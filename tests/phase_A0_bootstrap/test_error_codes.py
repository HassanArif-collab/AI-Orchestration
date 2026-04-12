"""
test_error_codes.py — Phase A.0: Tests for packages/core/error_codes.py

Covers:
  - ERROR_REGISTRY contains all expected error codes
  - ErrorDetail dataclass fields
  - get_error_detail() lookup
  - get_error_response() with valid and unknown codes
  - get_user_friendly_error() exception mapping
  - _map_exception_to_code() logic
"""

import pytest


class TestErrorRegistry:
    """Verify the ERROR_REGISTRY is complete and well-formed."""

    def test_registry_is_non_empty(self):
        from packages.core.error_codes import ERROR_REGISTRY
        assert len(ERROR_REGISTRY) > 0

    def test_all_expected_codes_present(self):
        from packages.core.error_codes import ERROR_REGISTRY
        expected_codes = {
            "NOTION_AUTH_FAILED", "NOTION_RATE_LIMIT", "NOTION_NOT_CONFIGURED",
            "NOTION_NOT_FOUND", "NOTION_CONNECTION_ERROR", "NOTION_PUBLISH_FAILED",
            "ZEP_UNAVAILABLE", "ZEP_NOT_CONFIGURED", "ZEP_RATE_LIMIT",
            "LLM_UNAVAILABLE", "LLM_RATE_LIMIT", "LLM_SERVICE_DOWN",
            "LLM_ALL_PROVIDERS_FAILED", "LLM_RESPONSE_PARSE_ERROR",
            "EXA_NOT_CONFIGURED", "EXA_SEARCH_FAILED", "EXA_RATE_LIMIT",
            "PIPELINE_STAGE_FAILED", "PIPELINE_QUALITY_FLOOR",
            "PIPELINE_INVALID_STATE",
            "INPUT_VALIDATION_FAILED", "VALIDATION_TOPIC_TOO_SHORT",
            "VALIDATION_TOPIC_TOO_LONG", "VALIDATION_EMPTY_FIELD",
            "DLQ_RETRY_FAILED", "CIRCUIT_BREAKER_OPEN",
            "SUPABASE_CONNECTION_FAILED", "SUPABASE_NOT_CONFIGURED",
            "YOUTUBE_AUTH_FAILED", "INTEGRATION_FAILED",
            "QUALITY_GATE_FAILED", "UNKNOWN_ERROR",
        }
        missing = expected_codes - set(ERROR_REGISTRY.keys())
        assert not missing, f"Missing error codes in registry: {missing}"

    def test_all_details_have_required_fields(self):
        from packages.core.error_codes import ERROR_REGISTRY, ErrorDetail
        required = {"user_message"}
        for code, detail in ERROR_REGISTRY.items():
            for field in required:
                assert hasattr(detail, field), f"{code} missing field: {field}"
                assert getattr(detail, field), f"{code} has empty {field}"

    def test_all_severities_are_valid(self):
        from packages.core.error_codes import ERROR_REGISTRY
        valid_severities = {"critical", "warning", "info", "low"}
        for code, detail in ERROR_REGISTRY.items():
            assert detail.severity in valid_severities, (
                f"{code} has invalid severity: {detail.severity}"
            )


class TestErrorDetail:
    """Tests for the ErrorDetail dataclass."""

    def test_creation(self):
        from packages.core.error_codes import ErrorDetail
        ed = ErrorDetail(user_message="Something went wrong")
        assert ed.user_message == "Something went wrong"
        assert ed.cause == ""
        assert ed.solution == ""

    def test_full_creation(self):
        from packages.core.error_codes import ErrorDetail
        ed = ErrorDetail(
            user_message="Error",
            cause="Because",
            solution="Fix it",
            action_button={"text": "Click", "link": "/settings"},
            severity="critical",
            icon="alert",
            retryable=True,
            recovery_time_seconds=30,
        )
        assert ed.suggested_action == "Fix it"
        assert ed.action_link == "/settings"
        assert ed.retryable is True

    def test_backward_compat_aliases(self):
        from packages.core.error_codes import ErrorDetail
        ed = ErrorDetail(user_message="E", solution="S", action_button={"link": "/x"})
        assert ed.suggested_action == "S"
        assert ed.action_link == "/x"


class TestGetErrorDetail:
    """Tests for get_error_detail() function."""

    def test_returns_detail_for_known_code(self):
        from packages.core.error_codes import get_error_detail, ErrorDetail
        detail = get_error_detail("NOTION_AUTH_FAILED")
        assert isinstance(detail, ErrorDetail)
        assert "Notion" in detail.user_message

    def test_returns_none_for_unknown_code(self):
        from packages.core.error_codes import get_error_detail
        assert get_error_detail("NONEXISTENT_CODE") is None


class TestGetErrorResponse:
    """Tests for get_error_response() function."""

    def test_valid_code_returns_dict(self):
        from packages.core.error_codes import get_error_response
        resp = get_error_response("LLM_UNAVAILABLE")
        assert isinstance(resp, dict)
        assert resp["error_code"] == "LLM_UNAVAILABLE"
        assert "user_message" in resp
        assert "cause" in resp
        assert "solution" in resp

    def test_unknown_code_returns_unknown_error(self):
        from packages.core.error_codes import get_error_response
        resp = get_error_response("FAKE_CODE")
        assert resp["error_code"] == "FAKE_CODE"
        assert resp["user_message"] == "An unexpected error occurred."

    def test_response_has_all_expected_keys(self):
        from packages.core.error_codes import get_error_response
        resp = get_error_response("LLM_RATE_LIMIT")
        expected_keys = {
            "error_code", "user_message", "cause", "solution",
            "action_button", "severity", "icon", "documentation_url",
            "retryable", "recovery_time_seconds",
        }
        assert set(resp.keys()) == expected_keys

    def test_retryable_errors(self):
        from packages.core.error_codes import get_error_response
        assert get_error_response("NOTION_RATE_LIMIT")["retryable"] is True
        assert get_error_response("ZEP_RATE_LIMIT")["retryable"] is True
        assert get_error_response("LLM_RATE_LIMIT")["retryable"] is True


class TestGetUserFriendlyError:
    """Tests for get_user_friendly_error() function."""

    def test_pipeline_exception_mapping(self):
        from packages.core.error_codes import get_user_friendly_error
        from packages.core.errors import LLMClientError
        exc = LLMClientError("FreeRouter not running")
        result = get_user_friendly_error(exc)
        assert result["error_code"] == "LLM_UNAVAILABLE"
        assert "technical_message" in result

    def test_rate_limit_exception(self):
        from packages.core.error_codes import get_user_friendly_error
        from packages.core.errors import RateLimitError
        exc = RateLimitError("429 Too Many Requests")
        result = get_user_friendly_error(exc)
        assert result["error_code"] == "LLM_RATE_LIMIT"

    def test_zep_exception(self):
        from packages.core.error_codes import get_user_friendly_error
        from packages.core.errors import ZepMemoryError
        exc = ZepMemoryError("Connection failed")
        result = get_user_friendly_error(exc)
        assert result["error_code"] == "ZEP_UNAVAILABLE"

    def test_quality_gate_exception(self):
        from packages.core.error_codes import get_user_friendly_error
        from packages.core.errors import QualityGateError
        exc = QualityGateError("Score too low")
        result = get_user_friendly_error(exc)
        assert result["error_code"] == "QUALITY_GATE_FAILED"

    def test_generic_exception_falls_back(self):
        from packages.core.error_codes import get_user_friendly_error
        exc = RuntimeError("something random")
        result = get_user_friendly_error(exc)
        assert result["error_code"] == "UNKNOWN_ERROR"
        assert result["technical_message"] == "something random"

    def test_connection_error_mapping(self):
        from packages.core.error_codes import get_user_friendly_error
        exc = ConnectionError("can't connect")
        result = get_user_friendly_error(exc)
        assert result["error_code"] == "LLM_UNAVAILABLE"

    def test_timeout_error_mapping(self):
        from packages.core.error_codes import get_user_friendly_error
        exc = TimeoutError("timed out")
        result = get_user_friendly_error(exc)
        assert result["error_code"] == "LLM_UNAVAILABLE"
