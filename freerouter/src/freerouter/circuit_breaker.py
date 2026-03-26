"""
circuit_breaker.py — Circuit breaker pattern for provider fault tolerance.

Context: Implements the circuit breaker pattern to prevent cascading failures
when providers become unavailable. Automatically trips after consecutive
failures and attempts recovery after a configured timeout.

Circuit States:
    CLOSED: Normal operation, requests flow through
    OPEN: Circuit tripped, requests fail fast without calling provider
    HALF_OPEN: Recovery mode, allows test request to check if provider recovered

Environment Variables:
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: Consecutive failures before tripping (default: 5)
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: Seconds before attempting recovery (default: 60)
    CIRCUIT_BREAKER_SUCCESS_THRESHOLD: Successes in half-open to close (default: 1)

Imports: nothing internal
Imported by: router.py
"""

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger("freerouter.circuit_breaker")


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast, not calling provider
    HALF_OPEN = "half_open"  # Testing if provider recovered


@dataclass
class CircuitStats:
    """Statistics for a circuit breaker instance."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_state_change: float = field(default_factory=time.time)
    total_failures: int = 0
    total_successes: int = 0
    total_rejections: int = 0  # Requests rejected while OPEN

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_state_change": self.last_state_change,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_rejections": self.total_rejections,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CircuitStats":
        """Deserialize from dictionary."""
        return cls(
            state=CircuitState(data.get("state", "closed")),
            failure_count=data.get("failure_count", 0),
            success_count=data.get("success_count", 0),
            last_failure_time=data.get("last_failure_time", 0.0),
            last_state_change=data.get("last_state_change", time.time()),
            total_failures=data.get("total_failures", 0),
            total_successes=data.get("total_successes", 0),
            total_rejections=data.get("total_rejections", 0),
        )


class CircuitBreaker:
    """Circuit breaker for a single provider.

    Implements the circuit breaker pattern to prevent cascading failures:
    - CLOSED (normal): Requests pass through, failures are counted
    - OPEN (tripped): Requests fail fast without calling provider
    - HALF_OPEN (recovery): Test requests allowed to check recovery

    Example:
        cb = CircuitBreaker("openai", failure_threshold=5, recovery_timeout=60)

        # Check before making request
        if cb.is_open():
            raise Exception("Circuit open, provider unavailable")

        try:
            result = await make_request()
            cb.record_success()
        except Exception as e:
            cb.record_failure()
            raise
    """

    def __init__(
        self,
        provider_name: str,
        failure_threshold: Optional[int] = None,
        recovery_timeout: Optional[int] = None,
        success_threshold: Optional[int] = None,
    ):
        """Initialize the circuit breaker.

        Args:
            provider_name: Name of the provider this circuit protects
            failure_threshold: Consecutive failures before tripping (default: from env or 5)
            recovery_timeout: Seconds before attempting recovery (default: from env or 60)
            success_threshold: Successes in half-open to close (default: from env or 1)
        """
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold or int(
            os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
        )
        self.recovery_timeout = recovery_timeout or int(
            os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60")
        )
        self.success_threshold = success_threshold or int(
            os.getenv("CIRCUIT_BREAKER_SUCCESS_THRESHOLD", "1")
        )
        self._stats = CircuitStats()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, with automatic recovery check."""
        # Check if we should transition from OPEN to HALF_OPEN
        if self._stats.state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to(CircuitState.HALF_OPEN)
        return self._stats.state

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        return (time.time() - self._stats.last_failure_time) >= self.recovery_timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new circuit state."""
        old_state = self._stats.state
        self._stats.state = new_state
        self._stats.last_state_change = time.time()

        # Reset counters on state change
        if new_state == CircuitState.CLOSED:
            self._stats.failure_count = 0
            self._stats.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._stats.success_count = 0

        logger.info(
            f"circuit_breaker_state_change: provider={self.provider_name} "
            f"old_state={old_state.value} new_state={new_state.value}"
        )

    def is_open(self) -> bool:
        """Check if the circuit is open (should fail fast).

        Returns:
            True if requests should be rejected (circuit is OPEN)
        """
        state = self.state
        if state == CircuitState.OPEN:
            self._stats.total_rejections += 1
            return True
        return False

    def is_closed(self) -> bool:
        """Check if the circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    def is_half_open(self) -> bool:
        """Check if the circuit is in half-open state (recovery testing)."""
        return self.state == CircuitState.HALF_OPEN

    def record_success(self) -> None:
        """Record a successful request."""
        self._stats.total_successes += 1

        if self.state == CircuitState.HALF_OPEN:
            self._stats.success_count += 1
            if self._stats.success_count >= self.success_threshold:
                logger.info(
                    f"circuit_breaker_recovered: provider={self.provider_name} "
                    f"success_count={self._stats.success_count}"
                )
                self._transition_to(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self._stats.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        self._stats.failure_count += 1
        self._stats.total_failures += 1
        self._stats.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Failure during recovery - go back to OPEN
            logger.warning(
                f"circuit_breaker_recovery_failed: provider={self.provider_name}"
            )
            self._transition_to(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED:
            if self._stats.failure_count >= self.failure_threshold:
                logger.warning(
                    f"circuit_breaker_tripped: provider={self.provider_name} "
                    f"failure_count={self._stats.failure_count} "
                    f"threshold={self.failure_threshold}"
                )
                self._transition_to(CircuitState.OPEN)

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        self._stats = CircuitStats()
        logger.info(f"circuit_breaker_reset: provider={self.provider_name}")

    def get_stats(self) -> CircuitStats:
        """Get current circuit breaker statistics."""
        return self._stats

    def get_stats_dict(self) -> dict:
        """Get current circuit breaker statistics as dictionary."""
        return self._stats.to_dict()


class CircuitBreakerManager:
    """Manages circuit breakers for multiple providers.

    Provides a central registry for circuit breakers with configurable
    defaults and provider-specific overrides.

    Example:
        manager = CircuitBreakerManager()

        # Get circuit for a provider
        circuit = manager.get_circuit("openai")

        # Check before request
        if circuit.is_open():
            skip_provider()
    """

    def __init__(
        self,
        default_failure_threshold: Optional[int] = None,
        default_recovery_timeout: Optional[int] = None,
        default_success_threshold: Optional[int] = None,
        provider_configs: Optional[dict[str, dict]] = None,
    ):
        """Initialize the circuit breaker manager.

        Args:
            default_failure_threshold: Default failures before tripping
            default_recovery_timeout: Default seconds before recovery
            default_success_threshold: Default successes to close from half-open
            provider_configs: Per-provider configuration overrides
        """
        self.default_failure_threshold = default_failure_threshold
        self.default_recovery_timeout = default_recovery_timeout
        self.default_success_threshold = default_success_threshold
        self.provider_configs = provider_configs or {}
        self._circuits: dict[str, CircuitBreaker] = {}

    def get_circuit(self, provider_name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            CircuitBreaker instance for the provider
        """
        if provider_name not in self._circuits:
            # Check for provider-specific config
            config = self.provider_configs.get(provider_name, {})
            self._circuits[provider_name] = CircuitBreaker(
                provider_name=provider_name,
                failure_threshold=config.get(
                    "failure_threshold", self.default_failure_threshold
                ),
                recovery_timeout=config.get(
                    "recovery_timeout", self.default_recovery_timeout
                ),
                success_threshold=config.get(
                    "success_threshold", self.default_success_threshold
                ),
            )
        return self._circuits[provider_name]

    def is_provider_available(self, provider_name: str) -> bool:
        """Check if a provider is available (circuit is not OPEN).

        Args:
            provider_name: Name of the provider

        Returns:
            True if provider is available, False if circuit is OPEN
        """
        circuit = self.get_circuit(provider_name)
        return not circuit.is_open()

    def record_success(self, provider_name: str) -> None:
        """Record a successful request for a provider."""
        self.get_circuit(provider_name).record_success()

    def record_failure(self, provider_name: str) -> None:
        """Record a failed request for a provider."""
        self.get_circuit(provider_name).record_failure()

    def reset_provider(self, provider_name: str) -> None:
        """Reset the circuit breaker for a provider."""
        if provider_name in self._circuits:
            self._circuits[provider_name].reset()

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for circuit in self._circuits.values():
            circuit.reset()

    def get_all_stats(self) -> dict[str, dict]:
        """Get statistics for all circuit breakers.

        Returns:
            Dict mapping provider names to their circuit stats
        """
        return {
            name: circuit.get_stats_dict()
            for name, circuit in self._circuits.items()
        }


# Global circuit breaker manager singleton
_manager: Optional[CircuitBreakerManager] = None


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager instance.

    Returns:
        CircuitBreakerManager singleton
    """
    global _manager
    if _manager is None:
        _manager = CircuitBreakerManager()
    return _manager


def get_circuit(provider_name: str) -> CircuitBreaker:
    """Get a circuit breaker for a provider (convenience function).

    Args:
        provider_name: Name of the provider

    Returns:
        CircuitBreaker instance for the provider
    """
    return get_circuit_breaker_manager().get_circuit(provider_name)


def is_provider_available(provider_name: str) -> bool:
    """Check if a provider is available (convenience function).

    Args:
        provider_name: Name of the provider

    Returns:
        True if provider is available (circuit not OPEN)
    """
    return get_circuit_breaker_manager().is_provider_available(provider_name)


def record_circuit_success(provider_name: str) -> None:
    """Record a successful request (convenience function)."""
    get_circuit_breaker_manager().record_success(provider_name)


def record_circuit_failure(provider_name: str) -> None:
    """Record a failed request (convenience function)."""
    get_circuit_breaker_manager().record_failure(provider_name)


def reset_circuit_breaker_manager() -> None:
    """Reset the global circuit breaker manager (for testing)."""
    global _manager
    _manager = None
