"""
test_circuit_breaker.py — Phase A.7: Tests for packages/core/circuit_breaker.py

Covers:
  - CircuitState enum values
  - CircuitBreaker initial state
  - State transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
  - allow_request() in each state
  - record_success() resets failure count, closes half_open
  - record_failure() increments count, opens circuit at threshold
  - reset() clears all state
  - get_status() dict structure
  - Custom thresholds (failure_threshold, recovery_timeout, half_open_max_calls)
  - Global registry: register, unregister, get_all_circuit_breaker_statuses
  - get_service_health_summary() (with mocked settings)
  - Thread safety basics
"""

import time
import pytest
from unittest.mock import patch, MagicMock


class TestCircuitState:
    """Tests for the CircuitState enum."""

    def test_state_values(self):
        from packages.core.circuit_breaker import CircuitState
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_default_state_is_closed(self):
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_default_failure_threshold(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.failure_threshold == 5

    def test_default_recovery_timeout(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.recovery_timeout == 30.0

    def test_default_half_open_max_calls(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.half_open_max_calls == 1

    def test_custom_name(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(name="test_service")
        assert cb.name == "test_service"

    def test_custom_threshold(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.failure_threshold == 3

    def test_custom_recovery_timeout(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(recovery_timeout=10.0)
        assert cb.recovery_timeout == 10.0

    def test_custom_half_open_max_calls(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(half_open_max_calls=3)
        assert cb.half_open_max_calls == 3


class TestClosedState:
    """Tests for circuit breaker behavior in CLOSED state."""

    def test_allow_request_in_closed(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.allow_request() is True

    def test_multiple_allow_requests_in_closed(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        for _ in range(10):
            assert cb.allow_request() is True

    def test_record_success_keeps_closed(self):
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_record_success_resets_failure_count(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        cb.record_failure()
        cb.record_failure()
        assert cb._failure_count == 2
        cb.record_success()
        assert cb._failure_count == 0


class TestOpenTransition:
    """Tests for CLOSED -> OPEN transition."""

    def test_opens_at_threshold(self):
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_deny_request_when_open(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.allow_request() is False

    def test_failure_count_tracking(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=5)
        for i in range(5):
            cb.record_failure()
        assert cb._failure_count == 5
        assert cb._total_failures == 5

    def test_total_failures_persists_after_reset(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb._total_failures == 2
        cb.reset()
        assert cb._total_failures == 2  # total is lifetime count

    def test_last_failure_time_set(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        before = time.time()
        cb.record_failure()
        after = time.time()
        assert before <= cb._last_failure_time <= after


class TestHalfOpenTransition:
    """Tests for OPEN -> HALF_OPEN -> CLOSED transitions."""

    def test_transitions_to_half_open_after_timeout(self):
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_allows_limited_requests(self):
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=2)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True  # 1st call
        assert cb.allow_request() is True  # 2nd call
        assert cb.allow_request() is False  # 3rd call denied

    def test_half_open_success_closes_circuit(self):
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self):
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()  # failure in half_open
        assert cb.state == CircuitState.OPEN  # should reopen

    def test_half_open_resets_failure_count_on_success(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.record_success()
        assert cb._failure_count == 0

    def test_state_property_auto_transitions(self):
        """Reading .state should auto-transition OPEN -> HALF_OPEN after timeout."""
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        # Just reading .state should trigger transition
        assert cb.state == CircuitState.HALF_OPEN


class TestReset:
    """Tests for CircuitBreaker.reset()."""

    def test_reset_returns_to_closed(self):
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_failure_count(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        cb.record_failure()
        cb.record_failure()
        cb.reset()
        assert cb._failure_count == 0

    def test_reset_clears_last_failure_time(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        cb.record_failure()
        cb.reset()
        assert cb._last_failure_time == 0

    def test_reset_clears_half_open_calls(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(half_open_max_calls=3)
        cb._half_open_calls = 2
        cb.reset()
        assert cb._half_open_calls == 0

    def test_reset_does_not_clear_totals(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        cb.record_success()
        cb.record_failure()
        cb.reset()
        assert cb._total_successes == 1
        assert cb._total_failures == 1


class TestGetStatus:
    """Tests for CircuitBreaker.get_status()."""

    def test_status_dict_keys(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(name="test")
        status = cb.get_status()
        expected_keys = {
            "name", "state", "failure_count", "last_failure_time",
            "recovery_timeout", "time_until_recovery",
            "total_successes", "total_failures",
            "failure_threshold", "half_open_max_calls",
        }
        assert set(status.keys()) == expected_keys

    def test_status_name(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(name="my_service")
        assert cb.get_status()["name"] == "my_service"

    def test_status_closed_state(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.get_status()["state"] == "closed"

    def test_status_open_state(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.get_status()["state"] == "open"

    def test_status_time_until_recovery_when_open(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0)
        cb.record_failure()
        status = cb.get_status()
        assert status["time_until_recovery"] > 0
        assert status["time_until_recovery"] <= 30.0

    def test_status_time_until_recovery_when_closed(self):
        from packages.core.circuit_breaker import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.get_status()["time_until_recovery"] == 0


class TestGlobalRegistry:
    """Tests for the global circuit breaker registry."""

    def test_register_and_retrieve(self):
        from packages.core.circuit_breaker import (
            CircuitBreaker, register_circuit_breaker, get_all_circuit_breaker_statuses,
        )
        cb = CircuitBreaker(name="test_registry")
        register_circuit_breaker(cb)
        statuses = get_all_circuit_breaker_statuses()
        assert "test_registry" in statuses

    def test_unregister(self):
        from packages.core.circuit_breaker import (
            CircuitBreaker, register_circuit_breaker,
            unregister_circuit_breaker, get_all_circuit_breaker_statuses,
        )
        cb = CircuitBreaker(name="to_remove")
        register_circuit_breaker(cb)
        unregister_circuit_breaker("to_remove")
        assert "to_remove" not in get_all_circuit_breaker_statuses()

    def test_unregister_nonexistent_silent(self):
        from packages.core.circuit_breaker import unregister_circuit_breaker
        # Should not raise
        unregister_circuit_breaker("does_not_exist")

    def test_multiple_circuit_breakers(self):
        from packages.core.circuit_breaker import (
            CircuitBreaker, register_circuit_breaker, get_all_circuit_breaker_statuses,
        )
        cb1 = CircuitBreaker(name="service_a")
        cb2 = CircuitBreaker(name="service_b")
        register_circuit_breaker(cb1)
        register_circuit_breaker(cb2)
        statuses = get_all_circuit_breaker_statuses()
        assert len(statuses) == 2
        assert "service_a" in statuses
        assert "service_b" in statuses

    def test_register_overwrites(self):
        from packages.core.circuit_breaker import (
            CircuitBreaker, register_circuit_breaker, get_all_circuit_breaker_statuses,
        )
        cb1 = CircuitBreaker(name="dup", failure_threshold=3)
        cb2 = CircuitBreaker(name="dup", failure_threshold=5)
        register_circuit_breaker(cb1)
        register_circuit_breaker(cb2)
        statuses = get_all_circuit_breaker_statuses()
        assert statuses["dup"]["failure_threshold"] == 5


class TestGetServiceHealthSummary:
    """Tests for get_service_health_summary()."""

    def test_healthy_with_no_open_circuits(self):
        from packages.core.circuit_breaker import (
            CircuitBreaker, register_circuit_breaker, get_service_health_summary,
        )
        cb = CircuitBreaker(name="healthy_cb")
        register_circuit_breaker(cb)

        mock_settings = MagicMock()
        mock_settings.get_service_status.return_value = {
            "zep": "available",
            "youtube": "not_configured",
            "notion": "available",
            "freerouter": "available",
            "supabase": "not_configured",
            "exa": "available",
        }
        # get_settings is imported lazily inside get_service_health_summary,
        # so we patch it at the config module level with create=True
        with patch("packages.core.config.get_settings", return_value=mock_settings):
            summary = get_service_health_summary()
        assert summary["overall_status"] == "degraded"  # not_configured services
        assert summary["open_circuits"] == []

    def test_unhealthy_with_open_circuits(self):
        from packages.core.circuit_breaker import (
            CircuitBreaker, register_circuit_breaker, get_service_health_summary,
        )
        cb = CircuitBreaker(name="broken_cb", failure_threshold=1)
        cb.record_failure()
        register_circuit_breaker(cb)

        mock_settings = MagicMock()
        mock_settings.get_service_status.return_value = {
            "zep": "available", "youtube": "available",
            "notion": "available", "freerouter": "available",
            "supabase": "available", "exa": "available",
        }
        with patch("packages.core.config.get_settings", return_value=mock_settings):
            summary = get_service_health_summary()
        assert summary["overall_status"] == "unhealthy"
        assert "broken_cb" in summary["open_circuits"]

    def test_settings_import_failure_handled(self):
        from packages.core.circuit_breaker import get_service_health_summary
        with patch("packages.core.config.get_settings", side_effect=Exception("fail")):
            summary = get_service_health_summary()
        assert summary["services"] == {}
        assert summary["overall_status"] == "healthy"


class TestEdgeCases:
    """Edge case tests for circuit breaker."""

    def test_single_failure_threshold(self):
        """Circuit should open after just 1 failure."""
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_very_large_threshold(self):
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=100)
        for _ in range(99):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_zero_recovery_timeout(self):
        """Recovery timeout of 0 should transition immediately to HALF_OPEN."""
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        cb.record_failure()
        # With recovery_timeout=0.0, reading .state auto-transitions OPEN -> HALF_OPEN
        # because time.time() - _last_failure_time >= 0.0 is always true
        assert cb.state == CircuitState.HALF_OPEN
        # Verify it still allows a request
        assert cb.allow_request() is True

    def test_interleaved_success_failure(self):
        from packages.core.circuit_breaker import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()  # 1
        cb.record_success()  # resets to 0
        cb.record_failure()  # 1
        cb.record_failure()  # 2
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()  # 3 -> opens
        assert cb.state == CircuitState.OPEN
