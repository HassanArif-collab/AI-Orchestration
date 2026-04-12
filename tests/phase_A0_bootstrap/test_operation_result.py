"""
test_operation_result.py — Phase A.0: Tests for packages/core/operation_result.py

Covers:
  - ErrorSeverity enum values
  - OperationResult.ok() factory
  - OperationResult.fail() factory
  - to_api_response() shape
  - Generic type parameter behavior
"""

import pytest


class TestErrorSeverity:
    """Tests for ErrorSeverity enum."""

    def test_severity_values(self):
        from packages.core.operation_result import ErrorSeverity
        expected = {"critical", "warning", "info", "low"}
        actual = {s.value for s in ErrorSeverity}
        assert actual == expected


class TestOperationResultOk:
    """Tests for OperationResult.ok() factory method."""

    def test_success_true(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.ok(data={"id": 1})
        assert result.success is True

    def test_data_set(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.ok(data={"id": 1})
        assert result.data == {"id": 1}

    def test_default_user_message(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.ok(data="test")
        assert result.user_message == "Success"

    def test_custom_user_message(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.ok(data="test", message="All good")
        assert result.user_message == "All good"

    def test_error_fields_default_none(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.ok(data="test")
        assert result.error_code is None
        assert result.error_message is None
        assert result.retryable is False
        assert result.retry_after_seconds is None

    def test_none_data(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.ok(data=None)
        assert result.data is None
        assert result.success is True


class TestOperationResultFail:
    """Tests for OperationResult.fail() factory method."""

    def test_success_false(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.fail("Something went wrong")
        assert result.success is False

    def test_error_message(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.fail("DB connection lost")
        assert result.error_message == "DB connection lost"

    def test_user_message_fallback(self):
        """If no user_message, it falls back to the message param."""
        from packages.core.operation_result import OperationResult
        result = OperationResult.fail("internal error")
        assert result.user_message == "internal error"

    def test_with_code(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.fail("fail", code="DB_001")
        assert result.error_code == "DB_001"

    def test_with_severity(self):
        from packages.core.operation_result import OperationResult, ErrorSeverity
        result = OperationResult.fail("fail", severity=ErrorSeverity.CRITICAL)
        assert result.severity == ErrorSeverity.CRITICAL

    def test_retryable(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.fail("fail", retryable=True, retry_after=30)
        assert result.retryable is True
        assert result.retry_after_seconds == 30

    def test_with_details(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.fail("fail", details={"attempt": 3})
        assert result.error_details == {"attempt": 3}

    def test_full_fail(self):
        from packages.core.operation_result import OperationResult, ErrorSeverity
        result = OperationResult.fail(
            message="Notion API failed",
            code="NOTION_001",
            severity=ErrorSeverity.WARNING,
            user_message="Could not save to Notion",
            retryable=True,
            retry_after=60,
            details={"status_code": 503},
        )
        assert result.success is False
        assert result.error_code == "NOTION_001"
        assert result.severity == ErrorSeverity.WARNING
        assert result.retry_after_seconds == 60


class TestToApiResponse:
    """Tests for to_api_response() method."""

    def test_success_response_shape(self):
        from packages.core.operation_result import OperationResult
        result = OperationResult.ok(data={"key": "value"}, message="Done")
        resp = result.to_api_response()
        assert resp["success"] is True
        assert resp["data"] == {"key": "value"}
        assert resp["message"] == "Done"

    def test_failure_response_shape(self):
        from packages.core.operation_result import OperationResult, ErrorSeverity
        result = OperationResult.fail(
            "fail", code="E001", severity=ErrorSeverity.CRITICAL,
            retryable=True, retry_after=30
        )
        resp = result.to_api_response()
        assert resp["success"] is False
        assert resp["error_code"] == "E001"
        assert resp["severity"] == "critical"
        assert resp["retryable"] is True
        assert resp["retry_after_seconds"] == 30
        # These should NOT be in the API response
        assert "data" not in resp or resp.get("data") is None
