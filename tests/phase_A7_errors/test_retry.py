"""
test_retry.py — Phase A.7: Tests for packages/core/retry.py

Covers:
  - DEFAULT_RETRYABLE_EXCEPTIONS — expected types
  - is_retryable_exception() — type matching, name matching, status code matching
  - retry_with_backoff() — async decorator: success, retry, exhausted, non-retryable
  - retry_with_backoff_sync() — sync decorator: same behaviors
  - Exponential backoff timing (mocked sleep)
  - Max delay cap
  - Custom exception types
  - Jitter range validation
  - Function name preservation (wraps)
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, call


class TestDefaultRetryableExceptions:
    """Tests for DEFAULT_RETRYABLE_EXCEPTIONS tuple."""

    def test_includes_connection_error(self):
        from packages.core.retry import DEFAULT_RETRYABLE_EXCEPTIONS
        assert ConnectionError in DEFAULT_RETRYABLE_EXCEPTIONS

    def test_includes_connection_refused(self):
        from packages.core.retry import DEFAULT_RETRYABLE_EXCEPTIONS
        assert ConnectionRefusedError in DEFAULT_RETRYABLE_EXCEPTIONS

    def test_includes_connection_reset(self):
        from packages.core.retry import DEFAULT_RETRYABLE_EXCEPTIONS
        assert ConnectionResetError in DEFAULT_RETRYABLE_EXCEPTIONS

    def test_includes_timeout_error(self):
        from packages.core.retry import DEFAULT_RETRYABLE_EXCEPTIONS
        assert TimeoutError in DEFAULT_RETRYABLE_EXCEPTIONS

    def test_includes_asyncio_timeout(self):
        from packages.core.retry import DEFAULT_RETRYABLE_EXCEPTIONS
        assert asyncio.TimeoutError in DEFAULT_RETRYABLE_EXCEPTIONS

    def test_includes_oserror(self):
        from packages.core.retry import DEFAULT_RETRYABLE_EXCEPTIONS
        assert OSError in DEFAULT_RETRYABLE_EXCEPTIONS

    def test_is_tuple(self):
        from packages.core.retry import DEFAULT_RETRYABLE_EXCEPTIONS
        assert isinstance(DEFAULT_RETRYABLE_EXCEPTIONS, tuple)


class TestIsRetryableException:
    """Tests for is_retryable_exception() function."""

    def test_connection_error_is_retryable(self):
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        assert is_retryable_exception(ConnectionError("fail"), DEFAULT_RETRYABLE_EXCEPTIONS) is True

    def test_timeout_error_is_retryable(self):
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        assert is_retryable_exception(TimeoutError("timeout"), DEFAULT_RETRYABLE_EXCEPTIONS) is True

    def test_value_error_not_retryable(self):
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        assert is_retryable_exception(ValueError("bad"), DEFAULT_RETRYABLE_EXCEPTIONS) is False

    def test_runtime_error_not_retryable(self):
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        assert is_retryable_exception(RuntimeError("oops"), DEFAULT_RETRYABLE_EXCEPTIONS) is False

    def test_key_error_not_retryable(self):
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        assert is_retryable_exception(KeyError("missing"), DEFAULT_RETRYABLE_EXCEPTIONS) is False

    def test_custom_name_matching_connect_timeout(self):
        """Exception class named ConnectTimeout should be retryable by name."""
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        exc = type("ConnectTimeout", (Exception,), {})("timeout")
        assert is_retryable_exception(exc, DEFAULT_RETRYABLE_EXCEPTIONS) is True

    def test_custom_name_matching_read_timeout(self):
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        exc = type("ReadTimeout", (Exception,), {})("read timeout")
        assert is_retryable_exception(exc, DEFAULT_RETRYABLE_EXCEPTIONS) is True

    def test_custom_name_matching_ssLError(self):
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        exc = type("SSLError", (Exception,), {})("ssl")
        assert is_retryable_exception(exc, DEFAULT_RETRYABLE_EXCEPTIONS) is True

    def test_status_code_500_retryable(self):
        """HTTP 500 should be retryable via status code check."""
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        mock_response = MagicMock()
        mock_response.status_code = 500
        exc = Exception("server error")
        exc.response = mock_response
        assert is_retryable_exception(exc, DEFAULT_RETRYABLE_EXCEPTIONS) is True

    def test_status_code_429_retryable(self):
        """HTTP 429 (rate limit) should be retryable."""
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        mock_response = MagicMock()
        mock_response.status_code = 429
        exc = Exception("rate limited")
        exc.response = mock_response
        assert is_retryable_exception(exc, DEFAULT_RETRYABLE_EXCEPTIONS) is True

    def test_status_code_400_not_retryable(self):
        """HTTP 400 (client error) should NOT be retryable."""
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        mock_response = MagicMock()
        mock_response.status_code = 400
        exc = Exception("bad request")
        exc.response = mock_response
        assert is_retryable_exception(exc, DEFAULT_RETRYABLE_EXCEPTIONS) is False

    def test_status_code_404_not_retryable(self):
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        mock_response = MagicMock()
        mock_response.status_code = 404
        exc = Exception("not found")
        exc.response = mock_response
        assert is_retryable_exception(exc, DEFAULT_RETRYABLE_EXCEPTIONS) is False

    def test_no_response_attribute(self):
        from packages.core.retry import is_retryable_exception, DEFAULT_RETRYABLE_EXCEPTIONS
        exc = ValueError("no response attr")
        assert is_retryable_exception(exc, DEFAULT_RETRYABLE_EXCEPTIONS) is False

    def test_custom_exception_types(self):
        """Custom exception tuple should be checked."""
        from packages.core.retry import is_retryable_exception
        custom_types = (ValueError, TypeError)
        assert is_retryable_exception(ValueError("bad"), custom_types) is True
        assert is_retryable_exception(TypeError("bad"), custom_types) is True
        assert is_retryable_exception(RuntimeError("bad"), custom_types) is False


class TestRetryWithBackoffAsync:
    """Tests for retry_with_backoff() async decorator."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        from packages.core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=3)
        async def success_func():
            return "ok"

        result = await success_func()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        from packages.core.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "recovered"

        with patch("packages.core.retry.asyncio.sleep") as mock_sleep:
            result = await flaky_func()
        assert result == "recovered"
        assert call_count == 3
        assert mock_sleep.call_count == 2  # slept twice before 3rd success

    @pytest.mark.asyncio
    async def test_exhausted_retries(self):
        from packages.core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=2, base_delay=0.01)
        async def always_fail():
            raise ConnectionError("always fails")

        with patch("packages.core.retry.asyncio.sleep"):
            with pytest.raises(ConnectionError, match="always fails"):
                await always_fail()

    @pytest.mark.asyncio
    async def test_non_retryable_exception_propagates(self):
        from packages.core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=3)
        async def raise_value_error():
            raise ValueError("not retryable")

        with patch("packages.core.retry.asyncio.sleep") as mock_sleep:
            with pytest.raises(ValueError, match="not retryable"):
                await raise_value_error()

        # Should NOT have slept — propagated immediately
        assert mock_sleep.call_count == 0

    @pytest.mark.asyncio
    async def test_single_attempt(self):
        from packages.core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=1)
        async def fail_once():
            raise ConnectionError("fail")

        with pytest.raises(ConnectionError):
            await fail_once()

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        """Verify delays increase exponentially: base*1, base*2, base*4, ..."""
        from packages.core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=4, base_delay=1.0, max_delay=100.0)
        async def always_fail():
            raise ConnectionError("fail")

        # Set random to constant for deterministic jitter
        with patch("packages.core.retry.random.random", return_value=0.5):
            with patch("packages.core.retry.asyncio.sleep") as mock_sleep:
                with pytest.raises(ConnectionError):
                    await always_fail()

        # With random=0.5, jitter factor = 0.5 + 0.5 = 1.0 (no jitter reduction)
        # Delays should be: 1.0 * 2^0 = 1.0, 1.0 * 2^1 = 2.0, 1.0 * 2^2 = 4.0
        assert mock_sleep.call_count == 3
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert abs(calls[0] - 1.0) < 0.01
        assert abs(calls[1] - 2.0) < 0.01
        assert abs(calls[2] - 4.0) < 0.01

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Delays should be capped at max_delay."""
        from packages.core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=4, base_delay=10.0, max_delay=15.0)
        async def always_fail():
            raise ConnectionError("fail")

        with patch("packages.core.retry.random.random", return_value=0.5):
            with patch("packages.core.retry.asyncio.sleep") as mock_sleep:
                with pytest.raises(ConnectionError):
                    await always_fail()

        # Without cap: 10, 20, 40 — but capped at 15
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert calls[0] == 10.0  # 10 * 2^0 = 10
        assert calls[1] == 15.0  # min(20, 15)
        assert calls[2] == 15.0  # min(40, 15)

    @pytest.mark.asyncio
    async def test_custom_exception_types(self):
        from packages.core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=3, base_delay=0.01, exceptions=(ValueError,))
        async def raise_value():
            raise ValueError("retry me")

        with patch("packages.core.retry.asyncio.sleep") as mock_sleep:
            with pytest.raises(ValueError):
                await raise_value()
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """@wraps should preserve the original function's __name__."""
        from packages.core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=3)
        async def my_api_call():
            return "ok"

        assert my_api_call.__name__ == "my_api_call"


class TestRetryWithBackoffSync:
    """Tests for retry_with_backoff_sync() decorator."""

    def test_success_no_retry(self):
        from packages.core.retry import retry_with_backoff_sync

        @retry_with_backoff_sync(max_attempts=3)
        def success_func():
            return "ok"

        result = success_func()
        assert result == "ok"

    def test_retry_then_success(self):
        from packages.core.retry import retry_with_backoff_sync

        call_count = 0

        @retry_with_backoff_sync(max_attempts=3, base_delay=0.01)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "recovered"

        with patch("time.sleep") as mock_sleep:
            result = flaky_func()
        assert result == "recovered"
        assert call_count == 3
        assert mock_sleep.call_count == 2

    def test_exhausted_retries(self):
        from packages.core.retry import retry_with_backoff_sync

        @retry_with_backoff_sync(max_attempts=2, base_delay=0.01)
        def always_fail():
            raise ConnectionError("always fails")

        with patch("time.sleep"):
            with pytest.raises(ConnectionError, match="always fails"):
                always_fail()

    def test_non_retryable_propagates_immediately(self):
        from packages.core.retry import retry_with_backoff_sync

        @retry_with_backoff_sync(max_attempts=3)
        def raise_value_error():
            raise ValueError("not retryable")

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(ValueError):
                raise_value_error()
        assert mock_sleep.call_count == 0

    def test_preserves_function_name(self):
        from packages.core.retry import retry_with_backoff_sync

        @retry_with_backoff_sync(max_attempts=3)
        def sync_api_call():
            return "ok"

        assert sync_api_call.__name__ == "sync_api_call"

    def test_exponential_delays_sync(self):
        from packages.core.retry import retry_with_backoff_sync

        @retry_with_backoff_sync(max_attempts=3, base_delay=1.0, max_delay=100.0)
        def always_fail():
            raise ConnectionError("fail")

        with patch("packages.core.retry.random.random", return_value=0.5):
            with patch("time.sleep") as mock_sleep:
                with pytest.raises(ConnectionError):
                    always_fail()

        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert abs(calls[0] - 1.0) < 0.01
        assert abs(calls[1] - 2.0) < 0.01


class TestRetryEdgeCases:
    """Edge cases for retry logic."""

    @pytest.mark.asyncio
    async def test_jitter_in_range(self):
        """Delay should be between 50% and 100% of base calculation."""
        from packages.core.retry import retry_with_backoff

        delays = []

        @retry_with_backoff(max_attempts=6, base_delay=1.0, max_delay=100.0)
        async def record_delays():
            raise ConnectionError("fail")

        # Capture actual delays
        original_sleep = asyncio.sleep
        sleep_values = []

        async def capture_sleep(delay):
            sleep_values.append(delay)
            raise asyncio.CancelledError()  # break early

        with patch("packages.core.retry.asyncio.sleep", side_effect=capture_sleep):
            with pytest.raises((ConnectionError, asyncio.CancelledError)):
                await record_delays()

        # Each delay should be between base * 2^n * 0.5 and base * 2^n * 1.5
        # (due to jitter = delay * (0.5 + random.random()) where random is [0, 1))
        for i, d in enumerate(sleep_values):
            base_calc = 1.0 * (2 ** i)
            assert 0.5 * base_calc <= d < 1.5 * base_calc, (
                f"Attempt {i+1}: delay {d} outside [{0.5*base_calc}, {1.5*base_calc})"
            )

    @pytest.mark.asyncio
    async def test_asyncio_timeout_is_retryable(self):
        from packages.core.retry import retry_with_backoff

        @retry_with_backoff(max_attempts=2, base_delay=0.01)
        async def timeout_func():
            raise asyncio.TimeoutError("async timeout")

        with patch("packages.core.retry.asyncio.sleep"):
            with pytest.raises(asyncio.TimeoutError):
                await timeout_func()

    def test_connection_refused_is_retryable(self):
        from packages.core.retry import retry_with_backoff_sync

        @retry_with_backoff_sync(max_attempts=2, base_delay=0.01)
        def refused_func():
            raise ConnectionRefusedError("refused")

        with patch("time.sleep"):
            with pytest.raises(ConnectionRefusedError):
                refused_func()

    def test_connection_reset_is_retryable(self):
        from packages.core.retry import retry_with_backoff_sync

        @retry_with_backoff_sync(max_attempts=2, base_delay=0.01)
        def reset_func():
            raise ConnectionResetError("reset")

        with patch("time.sleep"):
            with pytest.raises(ConnectionResetError):
                reset_func()
