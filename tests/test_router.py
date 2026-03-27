"""Tests for packages/router — client, capabilities, tracker."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from packages.router.capabilities import get_model_for_capability, list_capabilities
from packages.router.tracker import UsageTracker
from packages.router.client import RouterClient
from packages.core.errors import LLMClientError, RateLimitError


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


# ─── Tracker ──────────────────────────────────────────────────────────────────

def test_tracker_records_and_retrieves(tmp_path):
    tracker = UsageTracker(db_path=tmp_path / "test.db")
    tracker.record_call("groq", "llama-3.3-70b-versatile", 50, 150, 300, True)
    tracker.record_call("groq", "llama-3.3-70b-versatile", 80, 200, 250, True)
    usage = tracker.get_daily_usage("groq")
    assert usage["requests"] == 2
    assert usage["total_tokens"] == 480


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


# ─── RouterClient ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_raises_on_connection_refused():
    """When FreeRouter isn't running, should raise LLMClientError."""
    client = RouterClient(base_url="http://localhost:19999", startup_check=False)  # nothing on this port
    with pytest.raises(LLMClientError, match="Cannot connect"):
        await client.complete([{"role": "user", "content": "hi"}])
    await client.close()


@pytest.mark.asyncio
async def test_client_complete_mocked():
    """Mock the HTTP call and verify response parsing."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {
        "x-freerouter-provider": "groq",
        "x-freerouter-model": "llama-3.3-70b-versatile",
    }
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
    ok_response.headers = {"x-freerouter-provider": "openrouter", "x-freerouter-model": "stepfun"}
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
