"""
test_errors_hierarchy.py — Phase A.7: Additional tests for packages/core/errors.py

These tests complement the Phase A.0 test_errors.py suite. They cover
behaviors NOT already tested in A0:
  - str() and repr() representations
  - Catching via isinstance with intermediate classes
  - Instance-level error_code override precedence
  - get_error_code() edge cases
  - Error chaining and __cause__/__context__
  - PipelineException as generic Exception catch
  - QualityGateError with various parameter combos
"""

import pytest


class TestPipelineExceptionAdvanced:
    """Advanced tests for PipelineException (complementing A0)."""

    def test_str_representation_with_message(self):
        from packages.core.errors import PipelineException
        exc = PipelineException("detailed error message")
        assert str(exc) == "detailed error message"

    def test_str_empty_message(self):
        from packages.core.errors import PipelineException
        exc = PipelineException()
        assert str(exc) == ""

    def test_instance_error_code_overrides_class(self):
        """Instance-level error_code set via constructor should override class default."""
        from packages.core.errors import PipelineError
        # PipelineError class has error_code = "PIPELINE_STAGE_FAILED"
        exc = PipelineError("test", error_code="CUSTOM_OVERRIDE")
        assert exc.error_code == "CUSTOM_OVERRIDE"
        assert exc.get_error_code() == "CUSTOM_OVERRIDE"

    def test_class_error_code_unchanged_by_instance(self):
        """Setting instance error_code should NOT mutate the class attribute."""
        from packages.core.errors import PipelineError
        original = PipelineError.error_code
        exc = PipelineError("test", error_code="NEW_CODE")
        assert PipelineError.error_code == original

    def test_catch_as_generic_exception(self):
        """All PipelineException subclasses should be catchable as Exception."""
        from packages.core.errors import RateLimitError
        with pytest.raises(Exception):
            raise RateLimitError("test")

    def test_catch_pipeline_exception_base(self):
        """All subclasses should be catchable via PipelineException."""
        from packages.core.errors import (
            PipelineException, LLMClientError, RateLimitError,
            ZepMemoryError, PipelineError, IntegrationError, QualityGateError,
        )
        test_cases = [
            LLMClientError("llm"),
            RateLimitError("rate"),
            ZepMemoryError("zep"),
            PipelineError("pipeline"),
            IntegrationError("integration"),
            QualityGateError("quality"),
        ]
        for exc_instance in test_cases:
            try:
                raise exc_instance
            except PipelineException:
                pass  # Expected

    def test_rate_limit_catchable_as_llm_client(self):
        """RateLimitError should be catchable as LLMClientError (parent class)."""
        from packages.core.errors import RateLimitError, LLMClientError
        with pytest.raises(LLMClientError):
            raise RateLimitError("429")

    def test_error_code_attribute_default_empty(self):
        """PipelineException base class has empty default error_code."""
        from packages.core.errors import PipelineException
        exc = PipelineException("msg")
        assert exc.error_code == ""

    def test_get_error_code_with_instance_override(self):
        """get_error_code should prefer instance-level over class-level."""
        from packages.core.errors import IntegrationError
        exc = IntegrationError("msg", error_code="NOTION_RATE_LIMIT")
        assert exc.get_error_code() == "NOTION_RATE_LIMIT"

    def test_none_error_code_falls_back(self):
        """If error_code is explicitly None, should still use UNKNOWN_ERROR."""
        from packages.core.errors import PipelineException
        exc = PipelineException("msg", error_code=None)
        assert exc.get_error_code() == "UNKNOWN_ERROR"

    def test_has_args_attribute_like_builtin(self):
        """PipelineException should have .args like standard Python exceptions."""
        from packages.core.errors import PipelineException
        exc = PipelineException("message")
        assert exc.args == ("message",)

    def test_kwargs_only(self):
        from packages.core.errors import PipelineException
        exc = PipelineException(error_code="CUSTOM")
        assert str(exc) == ""
        assert exc.error_code == "CUSTOM"


class TestRateLimitErrorAdvanced:
    """Advanced tests for RateLimitError."""

    def test_rate_limit_inherits_error_code_from_class(self):
        """RateLimitError should inherit LLM_RATE_LIMIT from class, not LLM_UNAVAILABLE from parent."""
        from packages.core.errors import RateLimitError
        exc = RateLimitError("429")
        # Class-level error_code should be "LLM_RATE_LIMIT", not inherited from LLMClientError
        assert RateLimitError.error_code == "LLM_RATE_LIMIT"
        assert exc.get_error_code() == "LLM_RATE_LIMIT"

    def test_rate_limit_override_error_code(self):
        from packages.core.errors import RateLimitError
        exc = RateLimitError("429", error_code="ZEP_RATE_LIMIT")
        assert exc.get_error_code() == "ZEP_RATE_LIMIT"


class TestLLMClientErrorAdvanced:
    """Advanced tests for LLMClientError."""

    def test_llm_client_is_not_rate_limit(self):
        """LLMClientError should NOT be an instance of RateLimitError (child, not parent)."""
        from packages.core.errors import LLMClientError, RateLimitError
        exc = LLMClientError("fail")
        assert not isinstance(exc, RateLimitError)

    def test_llm_client_default_error_code(self):
        from packages.core.errors import LLMClientError
        exc = LLMClientError("fail")
        assert exc.get_error_code() == "LLM_UNAVAILABLE"


class TestZepMemoryErrorAdvanced:
    """Advanced tests for ZepMemoryError."""

    def test_zep_memory_error_code(self):
        from packages.core.errors import ZepMemoryError
        exc = ZepMemoryError("connection failed")
        assert exc.get_error_code() == "ZEP_UNAVAILABLE"

    def test_zep_memory_override(self):
        from packages.core.errors import ZepMemoryError
        exc = ZepMemoryError("fail", error_code="ZEP_NOT_CONFIGURED")
        assert exc.get_error_code() == "ZEP_NOT_CONFIGURED"


class TestIntegrationErrorAdvanced:
    """Advanced tests for IntegrationError."""

    def test_integration_error_with_message(self):
        from packages.core.errors import IntegrationError
        exc = IntegrationError("YouTube API returned 403")
        assert "YouTube" in str(exc)
        assert exc.get_error_code() == "INTEGRATION_FAILED"


class TestQualityGateErrorAdvanced:
    """Advanced tests for QualityGateError (complementing A0)."""

    def test_score_only(self):
        from packages.core.errors import QualityGateError
        exc = QualityGateError("score too low", score=45.0)
        assert exc.score == 45.0
        assert exc.floor is None

    def test_floor_only(self):
        from packages.core.errors import QualityGateError
        exc = QualityGateError("below floor", floor=60.0)
        assert exc.score is None
        assert exc.floor == 60.0

    def test_integer_score_and_floor(self):
        from packages.core.errors import QualityGateError
        exc = QualityGateError("fail", score=55, floor=60)
        assert exc.score == 55
        assert exc.floor == 60
        assert isinstance(exc.score, int)
        assert isinstance(exc.floor, int)

    def test_zero_score(self):
        from packages.core.errors import QualityGateError
        exc = QualityGateError("fail", score=0.0, floor=0.0)
        assert exc.score == 0.0
        assert exc.floor == 0.0

    def test_catchable_as_pipeline_exception(self):
        from packages.core.errors import QualityGateError, PipelineException
        with pytest.raises(PipelineException):
            raise QualityGateError("fail", score=50)


class TestExceptionChaining:
    """Tests for exception chaining patterns."""

    def test_raise_from(self):
        from packages.core.errors import PipelineError
        try:
            try:
                raise ValueError("original")
            except ValueError as e:
                raise PipelineError("wrapped") from e
        except PipelineError as caught:
            assert caught.__cause__ is not None
            assert isinstance(caught.__cause__, ValueError)
            assert str(caught.__cause__) == "original"

    def test_implicit_chaining(self):
        from packages.core.errors import IntegrationError
        try:
            try:
                raise ConnectionError("network")
            except ConnectionError:
                raise IntegrationError("service down")
        except IntegrationError as caught:
            assert caught.__context__ is not None
            assert isinstance(caught.__context__, ConnectionError)


class TestErrorDetailRegistryMapping:
    """Verify error codes on exceptions match ERROR_REGISTRY entries."""

    def test_all_exception_codes_in_registry(self):
        """Every exception class error_code should exist in ERROR_REGISTRY."""
        from packages.core.errors import (
            PipelineError, LLMClientError, RateLimitError,
            ZepMemoryError, IntegrationError, QualityGateError,
        )
        from packages.core.error_codes import ERROR_REGISTRY
        classes = [
            PipelineError, LLMClientError, RateLimitError,
            ZepMemoryError, IntegrationError, QualityGateError,
        ]
        for cls in classes:
            assert cls.error_code in ERROR_REGISTRY, (
                f"{cls.__name__}.error_code '{cls.error_code}' not in ERROR_REGISTRY"
            )
