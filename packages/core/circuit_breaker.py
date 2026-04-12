"""Circuit breaker pattern for protecting against cascading failures.

States:
  CLOSED  — Normal operation. Requests pass through.
  OPEN    — Failing. All requests rejected immediately.
  HALF_OPEN — Testing recovery. Limited requests allowed.

Provides:
  - CircuitBreaker: Thread-safe circuit breaker with configurable thresholds.
  - Global registry for tracking all circuit breakers.
  - Status reporting for service health dashboards.
"""

import time
import threading
from enum import Enum
from typing import Optional
from packages.core.logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Thread-safe circuit breaker with configurable thresholds.

    Args:
        name: Identifier for this circuit breaker (used in logs)
        failure_threshold: Number of failures before opening circuit (default 5)
        recovery_timeout: Seconds to wait before transitioning OPEN -> HALF_OPEN (default 30)
        half_open_max_calls: Number of test requests in HALF_OPEN state (default 1)
    """

    def __init__(self, name: str = "default", failure_threshold: int = 5,
                 recovery_timeout: float = 30.0, half_open_max_calls: int = 1):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._half_open_calls = 0
        self._lock = threading.Lock()
        self._total_successes = 0
        self._total_failures = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"circuit_breaker_half_open: {self.name}")
            return self._state

    def allow_request(self) -> bool:
        with self._lock:
            # Handle state transitions inside the lock to prevent race conditions
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"circuit_breaker_half_open: {self.name}")
            
            state = self._state
            if state == CircuitState.CLOSED:
                return True
            if state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            return False  # OPEN

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"circuit_breaker_closed: {self.name}")
            self._failure_count = 0
            self._total_successes += 1

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._total_failures += 1
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"circuit_breaker_open: {self.name} after {self._failure_count} failures")

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_failure_time = 0

    def get_status(self) -> dict:
        """Return a status dict for dashboard and health reporting.

        Returns:
            Dict with keys:
                name: Circuit breaker identifier
                state: Current state (closed/open/half_open)
                failure_count: Consecutive failures in current window
                last_failure_time: Unix timestamp of last failure (0 if never)
                recovery_timeout: Seconds until OPEN -> HALF_OPEN transition
                time_until_recovery: Seconds remaining until recovery (0 if closed/already recovered)
                total_successes: Lifetime success count
                total_failures: Lifetime failure count
                failure_threshold: Configured failure threshold
                half_open_max_calls: Configured max calls in half-open
        """
        current_state = self.state
        now = time.time()
        time_until = 0.0

        if current_state == CircuitState.OPEN:
            elapsed = now - self._last_failure_time
            time_until = max(0.0, self.recovery_timeout - elapsed)

        return {
            "name": self.name,
            "state": current_state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
            "recovery_timeout": self.recovery_timeout,
            "time_until_recovery": round(time_until, 1),
            "total_successes": self._total_successes,
            "total_failures": self._total_failures,
            "failure_threshold": self.failure_threshold,
            "half_open_max_calls": self.half_open_max_calls,
        }


# ─── Global Circuit Breaker Registry ─────────────────────────────────────────

_circuit_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def register_circuit_breaker(cb: CircuitBreaker) -> None:
    """Register a circuit breaker in the global registry.

    Allows the health dashboard to discover and report on all circuit
    breakers in the system.

    Args:
        cb: The CircuitBreaker instance to register.
    """
    with _registry_lock:
        _circuit_breakers[cb.name] = cb


def unregister_circuit_breaker(name: str) -> None:
    """Remove a circuit breaker from the global registry.

    Args:
        name: The name of the circuit breaker to unregister.
    """
    with _registry_lock:
        _circuit_breakers.pop(name, None)


def get_all_circuit_breaker_statuses() -> dict[str, dict]:
    """Return status for all registered circuit breakers.

    Returns:
        Dict mapping circuit breaker names to their status dicts
        (as returned by CircuitBreaker.get_status()).
    """
    with _registry_lock:
        return {
            name: cb.get_status()
            for name, cb in _circuit_breakers.items()
        }


def get_service_health_summary() -> dict:
    """Return a combined health summary of circuit breakers and config services.

    Combines:
    1. All registered circuit breaker statuses
    2. Configuration-based service status (from Settings.validate_service)

    Returns:
        Dict with keys:
            circuit_breakers: Dict of all CB statuses
            services: Dict of config-based service statuses
            overall_status: "healthy" | "degraded" | "unhealthy"
            open_circuits: List of names of open circuit breakers
    """
    # Circuit breaker statuses
    cb_statuses = get_all_circuit_breaker_statuses()
    open_circuits = [
        name
        for name, status in cb_statuses.items()
        if status["state"] == "open"
    ]

    # Config-based service statuses
    service_statuses: dict[str, str] = {}
    try:
        from packages.core.config import get_settings
        settings = get_settings()
        service_statuses = settings.get_service_status()
    except Exception:
        logger.debug("Could not load settings for service health summary")

    # Determine overall status
    if open_circuits:
        overall = "unhealthy"
    elif any(s == "not_configured" for s in service_statuses.values()):
        overall = "degraded"
    elif any(s == "misconfigured" for s in service_statuses.values()):
        overall = "degraded"
    elif any(s["state"] == "half_open" for s in cb_statuses.values()):
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "circuit_breakers": cb_statuses,
        "services": service_statuses,
        "overall_status": overall,
        "open_circuits": open_circuits,
    }
