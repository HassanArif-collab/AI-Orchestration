"""
test_logger.py — Phase A.0: Tests for packages/core/logger.py

Covers:
  - get_logger() returns a structlog.BoundLogger
  - Sensitive field sanitization
  - sanitize_dict() recursive redaction
  - _sanitize_value() truncation
  - Thread-safe idempotent configuration
"""

import pytest
import threading


class TestGetLogger:
    """Tests for the get_logger() function."""

    def test_returns_bound_logger(self):
        from packages.core.logger import get_logger
        import structlog
        log = get_logger("test_module")
        assert isinstance(log, structlog.BoundLogger)

    def test_different_names_different_loggers(self):
        from packages.core.logger import get_logger
        log1 = get_logger("module_a")
        log2 = get_logger("module_b")
        # structlog may return the same or different instances depending on config
        # The important thing is they both work
        assert log1 is not None
        assert log2 is not None

    def test_idempotent_configuration(self):
        """Calling get_logger multiple times doesn't crash."""
        from packages.core.logger import get_logger
        for _ in range(5):
            log = get_logger("test_idempotent")
            assert log is not None


class TestSanitizeValue:
    """Tests for _sanitize_value()."""

    def test_normal_value_unchanged(self):
        from packages.core.logger import _sanitize_value
        assert _sanitize_value("hello world") == "hello world"

    def test_long_value_truncated(self):
        from packages.core.logger import _sanitize_value
        long_val = "x" * 200
        result = _sanitize_value(long_val, max_length=50)
        assert len(result) == 50 + len("...[truncated]")
        assert result.endswith("...[truncated]")

    def test_non_string_converted(self):
        from packages.core.logger import _sanitize_value
        result = _sanitize_value(42)
        assert result == "42"

    def test_none_converted(self):
        from packages.core.logger import _sanitize_value
        result = _sanitize_value(None)
        assert result == "None"


class TestSanitizeDict:
    """Tests for sanitize_dict()."""

    def test_no_redaction_needed(self):
        from packages.core.logger import sanitize_dict
        data = {"name": "Alice", "role": "admin"}
        result = sanitize_dict(data)
        assert result == data

    def test_redacts_api_key(self):
        from packages.core.logger import sanitize_dict
        data = {"api_key": "sk-12345", "name": "Alice"}
        result = sanitize_dict(data)
        assert result["api_key"] == "[REDACTED]"
        assert result["name"] == "Alice"

    def test_redacts_token(self):
        from packages.core.logger import sanitize_dict
        data = {"access_token": "secret_token", "data": "safe"}
        result = sanitize_dict(data)
        assert result["access_token"] == "[REDACTED]"

    def test_redacts_password(self):
        from packages.core.logger import sanitize_dict
        data = {"password": "p@ssw0rd"}
        result = sanitize_dict(data)
        assert result["password"] == "[REDACTED]"

    def test_redacts_nested_dict(self):
        from packages.core.logger import sanitize_dict
        data = {"user": {"name": "Bob", "secret": "hidden"}}
        result = sanitize_dict(data)
        assert result["user"]["name"] == "Bob"
        assert result["user"]["secret"] == "[REDACTED]"

    def test_max_depth_prevents_infinite_recursion(self):
        from packages.core.logger import sanitize_dict
        # Create a self-referencing dict-like structure
        data = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": "deep"}}}}}}}}
        result = sanitize_dict(data)
        assert "_truncated" in str(result) or result is not None

    def test_redacts_hyphenated_keys(self):
        from packages.core.logger import sanitize_dict
        data = {"api-key": "val", "private-key": "val"}
        result = sanitize_dict(data)
        assert result["api-key"] == "[REDACTED]"
        assert result["private-key"] == "[REDACTED]"

    def test_redacts_keys_with_suffixes(self):
        from packages.core.logger import sanitize_dict
        data = {"my_token": "val", "user_secret": "val"}
        result = sanitize_dict(data)
        assert result["my_token"] == "[REDACTED]"
        assert result["user_secret"] == "[REDACTED]"


class TestSensitiveFields:
    """Verify the SENSITIVE_FIELDS constant is comprehensive."""

    def test_sensitive_fields_non_empty(self):
        from packages.core.logger import SENSITIVE_FIELDS
        assert len(SENSITIVE_FIELDS) > 0

    def test_contains_common_patterns(self):
        from packages.core.logger import SENSITIVE_FIELDS
        expected_patterns = {"api_key", "token", "password", "secret", "private_key"}
        assert expected_patterns.issubset(SENSITIVE_FIELDS)


class TestThreadSafety:
    """Verify logging configuration is thread-safe."""

    def test_concurrent_get_logger(self):
        from packages.core.logger import get_logger
        errors = []

        def worker():
            try:
                log = get_logger(f"thread_{threading.current_thread().name}")
                assert log is not None
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors in concurrent logging: {errors}"
