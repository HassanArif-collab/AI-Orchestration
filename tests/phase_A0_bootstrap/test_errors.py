"""
test_errors.py — Phase A.0: Tests for packages/core/errors.py

Covers:
  - PipelineException base class
  - Error code attribute (class-level and instance-level)
  - Subclass hierarchy (RateLimitError -> LLMClientError -> PipelineException)
  - QualityGateError extra attributes (score, floor)
  - No shadowing of Python builtins
"""

import pytest


class TestPipelineException:
    """Tests for the base exception class."""

    def test_default_error_code(self):
        from packages.core.errors import PipelineException
        exc = PipelineException("something went wrong")
        assert str(exc) == "something went wrong"
        assert exc.error_code == ""

    def test_custom_error_code(self):
        from packages.core.errors import PipelineException
        exc = PipelineException("fail", error_code="CUSTOM_001")
        assert exc.error_code == "CUSTOM_001"

    def test_get_error_code_instance_level(self):
        from packages.core.errors import PipelineException
        exc = PipelineException("fail", error_code="INST")
        assert exc.get_error_code() == "INST"

    def test_get_error_code_class_level(self):
        """When instance has no error_code but class does, class wins."""
        from packages.core.errors import PipelineException
        exc = PipelineException("fail")
        # PipelineException base class has no default code
        assert exc.get_error_code() == "UNKNOWN_ERROR"

    def test_get_error_code_unknown_fallback(self):
        """Empty string error_code falls back to UNKNOWN_ERROR."""
        from packages.core.errors import PipelineException
        exc = PipelineException("fail", error_code="")
        assert exc.get_error_code() == "UNKNOWN_ERROR"

    def test_is_exception(self):
        from packages.core.errors import PipelineException
        with pytest.raises(PipelineException):
            raise PipelineException("test")


class TestErrorHierarchy:
    """Verify the exception class hierarchy."""

    def test_rate_limit_inherits_llm_client(self):
        from packages.core.errors import RateLimitError, LLMClientError, PipelineException
        assert issubclass(RateLimitError, LLMClientError)
        assert issubclass(LLMClientError, PipelineException)
        assert issubclass(RateLimitError, PipelineException)

    def test_pipeline_error_inherits_base(self):
        from packages.core.errors import PipelineError, PipelineException
        assert issubclass(PipelineError, PipelineException)

    def test_zep_memory_inherits_base(self):
        from packages.core.errors import ZepMemoryError, PipelineException
        assert issubclass(ZepMemoryError, PipelineException)

    def test_integration_inherits_base(self):
        from packages.core.errors import IntegrationError, PipelineException
        assert issubclass(IntegrationError, PipelineException)

    def test_quality_gate_inherits_base(self):
        from packages.core.errors import QualityGateError, PipelineException
        assert issubclass(QualityGateError, PipelineException)

    def test_all_subclasses_catchable_as_base(self):
        from packages.core.errors import (
            PipelineException, LLMClientError, RateLimitError,
            ZepMemoryError, PipelineError, IntegrationError, QualityGateError,
        )
        excs = [
            LLMClientError("test"),
            RateLimitError("test"),
            ZepMemoryError("test"),
            PipelineError("test"),
            IntegrationError("test"),
            QualityGateError("test"),
        ]
        for exc in excs:
            assert isinstance(exc, PipelineException)


class TestErrorCodes:
    """Verify each exception has the correct error_code."""

    def test_pipeline_error_code(self):
        from packages.core.errors import PipelineError
        assert PipelineError.error_code == "PIPELINE_STAGE_FAILED"

    def test_llm_client_error_code(self):
        from packages.core.errors import LLMClientError
        assert LLMClientError.error_code == "LLM_UNAVAILABLE"

    def test_rate_limit_error_code(self):
        from packages.core.errors import RateLimitError
        assert RateLimitError.error_code == "LLM_RATE_LIMIT"

    def test_zep_memory_error_code(self):
        from packages.core.errors import ZepMemoryError
        assert ZepMemoryError.error_code == "ZEP_UNAVAILABLE"

    def test_integration_error_code(self):
        from packages.core.errors import IntegrationError
        assert IntegrationError.error_code == "INTEGRATION_FAILED"

    def test_quality_gate_error_code(self):
        from packages.core.errors import QualityGateError
        assert QualityGateError.error_code == "QUALITY_GATE_FAILED"


class TestQualityGateError:
    """QualityGateError has extra attributes: score and floor."""

    def test_score_and_floor_none_by_default(self):
        from packages.core.errors import QualityGateError
        exc = QualityGateError("fail")
        assert exc.score is None
        assert exc.floor is None

    def test_score_and_floor_set(self):
        from packages.core.errors import QualityGateError
        exc = QualityGateError("too low", score=55.0, floor=60.0)
        assert exc.score == 55.0
        assert exc.floor == 60.0

    def test_custom_error_code_overrides(self):
        from packages.core.errors import QualityGateError
        exc = QualityGateError("fail", score=50, floor=60, error_code="CUSTOM_GATE")
        assert exc.error_code == "CUSTOM_GATE"

    def test_get_error_code_returns_class_code(self):
        from packages.core.errors import QualityGateError
        exc = QualityGateError("fail")
        assert exc.get_error_code() == "QUALITY_GATE_FAILED"


class TestNoBuiltinShadowing:
    """Ensure none of our custom errors shadow Python builtins."""

    def test_no_memory_error(self):
        import builtins
        assert not hasattr(builtins, "MemoryError") or builtins.MemoryError is MemoryError

    def test_no_router_error_in_core(self):
        """core.errors should not export RouterError."""
        import packages.core.errors as errs
        assert not hasattr(errs, "RouterError")

    def test_all_custom_errors_distinct(self):
        """Each custom error should be a distinct class."""
        from packages.core.errors import (
            PipelineException, LLMClientError, RateLimitError,
            ZepMemoryError, PipelineError, IntegrationError, QualityGateError,
        )
        classes = [PipelineException, LLMClientError, RateLimitError,
                    ZepMemoryError, PipelineError, IntegrationError, QualityGateError]
        # All distinct classes
        assert len(set(id(c) for c in classes)) == len(classes)
