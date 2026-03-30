"""Tests for packages/router — client, capabilities, tracker."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from packages.router.capabilities import get_model_for_capability, list_capabilities
from packages.router.tracker import UsageTracker
from packages.router.client import RouterClient, _parse_provider_limits
from packages.core.errors import LLMClientError, RateLimitError
import httpx


# ─── Capabilities ─────────────────────────────────────────────────────────────

def test_known_capability_returns_model():
    model = get_model_for_capability("research")
    assert "/" in model  # format: "provider/model"


def test_unknown_capability_returns_auto():
    assert get_model_for_capability("nonexistent") == "auto"


def test_all_capabilities_listed():
    caps = list_capabilities()
    assert "research" in caps
    assert "scripting" in caps
    assert len(caps) >= 5


# ─── Rate Limit Header Parsing (Phase 3) ───────────────────────────────────────

def test_parse_provider_limits_with_headers():
    """When provider sends rate limit headers, parse them correctly."""
    mock_headers = httpx.Headers({
        "x-ratelimit-remaining-requests": "500",
        "x-ratelimit-remaining-tokens": "10000",
    })
    result = _parse_provider_limits(mock_headers, "groq")
    assert result["rpm_remaining"] == 500
    assert result["tpm_remaining"] == 10000
    assert result["provider"] == "groq"
    assert "timestamp" in result


def test_parse_provider_limits_missing_headers_returns_minus_one():
    """When provider doesn't send headers (e.g., Ollama), return -1."""
    mock_headers = httpx.Headers({})
    result = _parse_provider_limits(mock_headers, "ollama")
    assert result["rpm_remaining"] == -1
    assert result["tpm_remaining"] == -1
    assert result["provider"] == "ollama"


def test_parse_provider_limits_partial_headers():
    """When only some headers are present, others should be -1."""
    mock_headers = httpx.Headers({
        "x-ratelimit-remaining-requests": "100",
    })
    result = _parse_provider_limits(mock_headers, "openrouter")
    assert result["rpm_remaining"] == 100
    assert result["tpm_remaining"] == -1


# ─── Tracker ──────────────────────────────────────────────────────────────────

def test_tracker_records_and_retrieves(tmp_path):
    tracker = UsageTracker(db_path=tmp_path / "test.db")
    tracker.record_call("groq", "llama-3.3-70b-versatile", 50, 150, 300, True)
    tracker.record_call("groq", "llama-3.3-70b-versatile", 80, 200, 250, True)
    usage = tracker.get_daily_usage("groq")
    assert usage["requests"] == 2
    assert usage["total_tokens"] == 480


def test_tracker_records_live_rate_limits(tmp_path):
    """Tracker should accept and store rpm_remaining and tpm_remaining."""
    tracker = UsageTracker(db_path=tmp_path / "test.db")
    tracker.record_call(
        "groq", "llama-3.3-70b-versatile", 50, 150, 300, True,
        rpm_remaining=500, tpm_remaining=10000
    )
    limits = tracker.get_latest_limits()
    assert len(limits) == 1
    assert limits[0]["provider"] == "groq"
    assert limits[0]["live_rpm_remaining"] == 500
    assert limits[0]["live_tpm_remaining"] == 10000


def test_tracker_near_limit_false_at_low_usage(tmp_path):
    tracker = UsageTracker(db_path=tmp_path / "test.db")
    tracker.record_call("groq", "llama", 10, 10, 100, True)
    assert tracker.is_near_limit("groq") is False


def test_tracker_unknown_provider_not_near_limit(tmp_path):
    tracker = UsageTracker(db_path=tmp_path / "test.db")
    assert tracker.is_near_limit("unknown_provider") is False


def test_tracker_all_usage_today(tmp_path):
    tracker = UsageTracker(db_path=tmp_path / "test.db")
    tracker.record_call("groq", "llama", 10, 20, 100, True)
    tracker.record_call("openrouter", "stepfun", 5, 15, 200, True)
    all_usage = tracker.get_all_usage_today()
    providers = [u["provider"] for u in all_usage]
    assert "groq" in providers
    assert "openrouter" in providers


def test_tracker_get_latest_limits_multiple_providers(tmp_path):
    """get_latest_limits should return the most recent entry per provider."""
    tracker = UsageTracker(db_path=tmp_path / "test.db")
    tracker.record_call("groq", "llama", 10, 20, 100, True, rpm_remaining=100, tpm_remaining=5000)
    tracker.record_call("groq", "llama", 10, 20, 100, True, rpm_remaining=50, tpm_remaining=2500)  # newer
    tracker.record_call("openrouter", "stepfun", 5, 10, 200, True, rpm_remaining=80, tpm_remaining=8000)
    
    limits = tracker.get_latest_limits()
    providers = {l["provider"]: l for l in limits}
    
    assert "groq" in providers
    assert "openrouter" in providers
    # Should get the most recent (50, 2500) not the older (100, 5000)
    assert providers["groq"]["live_rpm_remaining"] == 50
    assert providers["groq"]["live_tpm_remaining"] == 2500


# ─── RouterClient ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_raises_on_connection_refused():
    """When FreeRouter isn't running, should raise LLMClientError."""
    client = RouterClient(base_url="http://localhost:19999", startup_check=False)  # nothing on this port
    with pytest.raises(LLMClientError, match="Cannot connect"):
        await client.complete([{"role": "user", "content": "hi"}])
    await client.close()


@pytest.mark.asyncio
async def test_client_complete_returns_dict_with_content_and_limits():
    """RouterClient.complete() should return dict with content and limits keys."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = httpx.Headers({
        "x-freerouter-provider": "groq",
        "x-freerouter-model": "llama-3.3-70b-versatile",
        "x-ratelimit-remaining-requests": "500",
        "x-ratelimit-remaining-tokens": "10000",
    })
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello!"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    mock_response.raise_for_status = MagicMock()

    client = RouterClient(base_url="http://localhost:4000", startup_check=False)
    with patch.object(client._http, "post", new=AsyncMock(return_value=mock_response)):
        result = await client.complete([{"role": "user", "content": "hi"}])

    assert "content" in result
    assert "limits" in result
    assert result["content"] == "Hello!"
    assert result["limits"]["rpm_remaining"] == 500
    assert result["limits"]["tpm_remaining"] == 10000
    assert result["provider"] == "groq"
    assert result["model"] == "llama-3.3-70b-versatile"
    await client.close()


@pytest.mark.asyncio
async def test_client_complete_mocked():
    """Mock the HTTP call and verify response parsing."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = httpx.Headers({
        "x-freerouter-provider": "groq",
        "x-freerouter-model": "llama-3.3-70b-versatile",
    })
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello!"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    mock_response.raise_for_status = MagicMock()

    client = RouterClient(base_url="http://localhost:4000", startup_check=False)
    with patch.object(client._http, "post", new=AsyncMock(return_value=mock_response)):
        result = await client.complete([{"role": "user", "content": "hi"}])

    assert result["content"] == "Hello!"
    assert result["provider"] == "groq"
    assert result["model"] == "llama-3.3-70b-versatile"
    assert result["usage"]["total_tokens"] == 15
    await client.close()


@pytest.mark.asyncio
async def test_client_retries_503_with_auto():
    """When specific model returns 503, should retry with model=auto."""
    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.headers = httpx.Headers({"x-freerouter-provider": "openrouter", "x-freerouter-model": "stepfun"})
    ok_response.json.return_value = {
        "choices": [{"message": {"content": "Fallback response"}}],
        "usage": {},
    }
    ok_response.raise_for_status = MagicMock()

    fail_response = MagicMock()
    fail_response.status_code = 503

    client = RouterClient(base_url="http://localhost:4000", startup_check=False)
    call_count = 0

    async def mock_post(path, json=None, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return fail_response   # first call: 503
        return ok_response         # second call: 200

    with patch.object(client._http, "post", side_effect=mock_post):
        result = await client.complete(
            [{"role": "user", "content": "hi"}],
            model="groq/llama-3.3-70b-versatile",
        )

    assert call_count == 2, "Should have retried once"
    assert result["content"] == "Fallback response"
    await client.close()


# ─── Agent Model Assignments (Phase 3) ────────────────────────────────────────

def test_researcher_uses_gemini():
    """Deep research should use Gemini for massive context window."""
    import subprocess
    result = subprocess.run(
        ["grep", "-n", "gemini-1.5-pro", 
         "packages/content_factory/production/deep_research.py"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, "Deep research should use Gemini 1.5 Pro"


def test_scoring_uses_llama70b():
    """Scoring engine should use Llama 70b on Groq for fast evaluation."""
    import subprocess
    result = subprocess.run(
        ["grep", "-n", "llama-3.3-70b-versatile", 
         "packages/content_factory/evaluation/scoring.py"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, "Scoring should use Llama 70b on Groq"


def test_challenger_uses_llama70b():
    """Challenger generator should use Llama 70b on Groq."""
    import subprocess
    result = subprocess.run(
        ["grep", "-n", "llama-3.3-70b-versatile", 
         "packages/content_factory/evaluation/mutation.py"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, "Challenger should use Llama 70b on Groq"


def test_visual_uses_ollama():
    """Visual annotator should use Ollama for local/free text categorization."""
    import subprocess
    result = subprocess.run(
        ["grep", "-n", "ollama/llama3.2", 
         "packages/pipeline/handlers.py"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, "Visual annotator should use Ollama"


def test_topic_finder_uses_gemini_flash():
    """Topic finder should use Gemini Flash for fast discovery."""
    import subprocess
    result = subprocess.run(
        ["grep", "-n", "gemini-2.0-flash", 
         "packages/content_factory/topic_finder/finder.py"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, "Topic finder should use Gemini Flash"
