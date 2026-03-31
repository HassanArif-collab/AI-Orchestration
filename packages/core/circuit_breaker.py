"""Circuit breaker pattern for protecting against cascading failures.

States:
  CLOSED  — Normal operation. Requests pass through.
  OPEN    — Failing. All requests rejected immediately.
  HALF_OPEN — Testing recovery. Limited requests allowed.
"""

import time
import threading
from enum import Enum
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

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"circuit_breaker_open: {self.name} after {self._failure_count} failures")

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_failure_time = 0
