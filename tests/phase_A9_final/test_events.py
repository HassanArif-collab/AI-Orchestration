"""
Phase A.9 Batch C — tests for apps/api/events.py
EventBus, sse_endpoint, and 8 emitter helpers.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from apps.api.events import (
    EventBus,
    emit_human_gate,
    emit_iteration_complete,
    emit_pipeline_complete,
    emit_pipeline_update,
    emit_provider_status,
    emit_rate_limit,
    emit_stage_complete,
    emit_task_created,
    sse_endpoint,
)


# ─── EventBus Core ────────────────────────────────────────────────────────


class TestEventBusInit:
    """Test EventBus initialisation."""

    def test_new_bus_has_no_subscribers(self):
        bus = EventBus()
        assert bus._subscribers == []

    def test_subscribe_returns_queue(self):
        bus = EventBus()
        q = bus.subscribe()
        assert isinstance(q, asyncio.Queue)
        assert q.maxsize == 50

    def test_subscribe_adds_to_subscribers(self):
        bus = EventBus()
        q = bus.subscribe()
        assert len(bus._subscribers) == 1
        assert bus._subscribers[0] is q


class TestEventBusUnsubscribe:
    """Test EventBus.unsubscribe."""

    def test_unsubscribe_removes_queue(self):
        bus = EventBus()
        q = bus.subscribe()
        bus.unsubscribe(q)
        assert q not in bus._subscribers
        assert len(bus._subscribers) == 0

    def test_unsubscribe_idempotent(self):
        bus = EventBus()
        q = bus.subscribe()
        bus.unsubscribe(q)  # first
        bus.unsubscribe(q)  # second — should not raise
        assert len(bus._subscribers) == 0

    def test_unsubscribe_wrong_queue_no_op(self):
        bus = EventBus()
        q1 = bus.subscribe()
        q2 = EventBus().subscribe()  # different bus, different queue
        bus.unsubscribe(q2)
        assert q1 in bus._subscribers


class TestEventBusPublish:
    """Test EventBus.publish."""

    @pytest.mark.asyncio
    async def test_publish_to_one_subscriber(self):
        bus = EventBus()
        q = bus.subscribe()
        await bus.publish("test_event", {"key": "value"})
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["type"] == "test_event"
        assert msg["data"] == {"key": "value"}
        assert "timestamp" in msg

    @pytest.mark.asyncio
    async def test_publish_to_multiple_subscribers(self):
        bus = EventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        await bus.publish("multi", {"n": 2})
        msg1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        msg2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert msg1["type"] == "multi"
        assert msg2["type"] == "multi"
        assert msg1["data"] == {"n": 2}

    @pytest.mark.asyncio
    async def test_publish_with_no_subscribers(self):
        bus = EventBus()
        # Should not raise
        await bus.publish("orphan", {})

    @pytest.mark.asyncio
    async def test_publish_message_has_iso_timestamp(self):
        bus = EventBus()
        q = bus.subscribe()
        await bus.publish("ts", {})
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        ts = msg["timestamp"]
        # ISO format should end with Z or +00:00
        assert ts.endswith("Z") or "+00:00" in ts


class TestEventBusQueueFull:
    """Test that full queues are removed (dead subscriber cleanup)."""

    @pytest.mark.asyncio
    async def test_full_queue_removed_on_publish(self):
        bus = EventBus()
        # Create a queue and fill it to maxsize
        q = asyncio.Queue(maxsize=1)
        q.put_nowait({"filler": True})  # fill the only slot
        bus._subscribers.append(q)

        await bus.publish("overflow", {})
        # The full queue should have been removed
        assert q not in bus._subscribers

    @pytest.mark.asyncio
    async def test_non_full_queue_kept(self):
        bus = EventBus()
        q = bus.subscribe()  # maxsize=50, empty
        await bus.publish("keep", {})
        assert q in bus._subscribers

    @pytest.mark.asyncio
    async def test_multiple_full_queues_all_removed(self):
        bus = EventBus()
        q1 = asyncio.Queue(maxsize=1)
        q1.put_nowait(True)
        q2 = asyncio.Queue(maxsize=1)
        q2.put_nowait(True)
        bus._subscribers = [q1, q2]

        await bus.publish("clean", {})
        assert q1 not in bus._subscribers
        assert q2 not in bus._subscribers


# ─── SSE Endpoint ─────────────────────────────────────────────────────────


class TestSSEEndpoint:
    """Test sse_endpoint StreamingResponse generation."""

    @pytest.mark.asyncio
    async def test_sse_format(self):
        """Verify SSE lines have correct event:/data: format."""
        bus = EventBus()
        request = MagicMock(spec=Request)
        request.is_disconnected = AsyncMock(side_effect=[False, True])

        # Patch wait_for to return a message immediately (avoids timing issues)
        mock_msg = {
            "type": "sse_test",
            "data": {"msg": "hello"},
            "timestamp": "2025-01-01T00:00:00+00:00",
        }
        with patch("apps.api.events.event_bus", bus), \
             patch("apps.api.events.asyncio.wait_for", new_callable=AsyncMock, return_value=mock_msg):
            response = await sse_endpoint(request)
            body_parts = []
            async for chunk in response.body_iterator:
                body_parts.append(chunk)

        full_body = "".join(body_parts)
        assert "event: sse_test" in full_body
        assert "data: " in full_body
        parsed = json.loads(full_body.split("data: ", 1)[1].split("\n", 1)[0])
        assert parsed["type"] == "sse_test"
        assert parsed["data"]["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_sse_keepalive_on_timeout(self):
        """When no events arrive within 15s, a keepalive comment is sent."""
        bus = EventBus()
        request = MagicMock(spec=Request)
        # First is_disconnected=False -> enters wait_for -> TimeoutError -> keepalive
        # Second is_disconnected=True -> break
        request.is_disconnected = AsyncMock(side_effect=[False, True])

        with patch("apps.api.events.event_bus", bus), \
             patch("apps.api.events.asyncio.wait_for", new_callable=AsyncMock) as mock_wf:
            mock_wf.side_effect = [asyncio.TimeoutError()]
            response = await sse_endpoint(request)
            body_parts = []
            async for chunk in response.body_iterator:
                body_parts.append(chunk)

        full_body = "".join(body_parts)
        assert ": keepalive" in full_body

    @pytest.mark.asyncio
    async def test_sse_unsubscribes_on_disconnect(self):
        """Ensure the subscriber is removed when client disconnects."""
        bus = EventBus()
        initial_count = len(bus._subscribers)

        request = MagicMock(spec=Request)
        request.is_disconnected = AsyncMock(return_value=True)  # immediate disconnect

        response = await sse_endpoint(request)
        # Drain the generator to trigger finally block
        async for _ in response.body_iterator:
            pass

        assert len(bus._subscribers) == initial_count  # no extra subscriber left

    @pytest.mark.asyncio
    async def test_sse_response_headers(self):
        """Check StreamingResponse has correct media type and headers."""
        request = MagicMock(spec=Request)
        request.is_disconnected = AsyncMock(return_value=True)

        response = await sse_endpoint(request)
        assert response.media_type == "text/event-stream"
        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("Connection") == "keep-alive"


# ─── Emitter Helpers ──────────────────────────────────────────────────────


class TestEmitterHelpers:
    """Each emitter should publish an event with the correct type and payload."""

    @pytest.mark.asyncio
    async def test_emit_pipeline_update(self):
        bus = EventBus()
        q = bus.subscribe()
        with patch("apps.api.events.event_bus", bus):
            await emit_pipeline_update("run-1", "research", "in_progress")
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["type"] == "pipeline_update"
        assert msg["data"]["run_id"] == "run-1"
        assert msg["data"]["stage"] == "research"
        assert msg["data"]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_emit_stage_complete(self):
        bus = EventBus()
        q = bus.subscribe()
        with patch("apps.api.events.event_bus", bus):
            await emit_stage_complete("run-2", "research", "Found 5 sources")
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["type"] == "stage_complete"
        assert msg["data"]["summary"] == "Found 5 sources"

    @pytest.mark.asyncio
    async def test_emit_stage_complete_default_summary(self):
        bus = EventBus()
        q = bus.subscribe()
        with patch("apps.api.events.event_bus", bus):
            await emit_stage_complete("run-3", "draft")
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["data"]["summary"] == ""

    @pytest.mark.asyncio
    async def test_emit_human_gate(self):
        bus = EventBus()
        q = bus.subscribe()
        with patch("apps.api.events.event_bus", bus):
            await emit_human_gate("run-4", "review")
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["type"] == "human_gate"
        assert msg["data"]["run_id"] == "run-4"
        assert msg["data"]["stage"] == "review"

    @pytest.mark.asyncio
    async def test_emit_pipeline_complete(self):
        bus = EventBus()
        q = bus.subscribe()
        with patch("apps.api.events.event_bus", bus):
            await emit_pipeline_complete("run-5")
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["type"] == "pipeline_complete"
        assert msg["data"]["run_id"] == "run-5"

    @pytest.mark.asyncio
    async def test_emit_provider_status(self):
        bus = EventBus()
        q = bus.subscribe()
        with patch("apps.api.events.event_bus", bus):
            await emit_provider_status("openai", "rate_limited")
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["type"] == "provider_status"
        assert msg["data"]["provider"] == "openai"
        assert msg["data"]["status"] == "rate_limited"

    @pytest.mark.asyncio
    async def test_emit_iteration_complete(self):
        bus = EventBus()
        q = bus.subscribe()
        with patch("apps.api.events.event_bus", bus):
            await emit_iteration_complete(
                run_id="run-6",
                iteration=3,
                score=92.5,
                previous_score=88.0,
                mutation_zone="hook",
                beat_baseline=True,
            )
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["type"] == "iteration_complete"
        d = msg["data"]
        assert d["run_id"] == "run-6"
        assert d["iteration"] == 3
        assert d["score"] == 92.5
        assert d["previous_score"] == 88.0
        assert d["delta"] == 4.5
        assert d["mutation_zone"] == "hook"
        assert d["beat_baseline"] is True
        assert d["script_json"] is None

    @pytest.mark.asyncio
    async def test_emit_iteration_complete_with_script(self):
        bus = EventBus()
        q = bus.subscribe()
        script = {"title": "Test Script", "body": "..."}
        with patch("apps.api.events.event_bus", bus):
            await emit_iteration_complete(
                run_id="run-7", iteration=0, score=80.0,
                previous_score=80.0, mutation_zone="intro",
                beat_baseline=False, script_json=script,
            )
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["data"]["script_json"] == script
        assert msg["data"]["beat_baseline"] is False
        assert msg["data"]["delta"] == 0.0

    @pytest.mark.asyncio
    async def test_emit_task_created(self):
        bus = EventBus()
        q = bus.subscribe()
        task_data = {"task_id": "t-1", "title": "Write script"}
        with patch("apps.api.events.event_bus", bus):
            await emit_task_created(task_data)
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["type"] == "task_created"
        assert msg["data"] == {"task_id": "t-1", "title": "Write script"}

    @pytest.mark.asyncio
    async def test_emit_rate_limit(self):
        bus = EventBus()
        q = bus.subscribe()
        with patch("apps.api.events.event_bus", bus):
            await emit_rate_limit(wait_time=30, attempt=2, max_retries=5, model="gpt-4o")
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["type"] == "rate_limit"
        d = msg["data"]
        assert d["wait_time"] == 30
        assert d["attempt"] == 2
        assert d["max_retries"] == 5
        assert d["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_emit_rate_limit_defaults(self):
        bus = EventBus()
        q = bus.subscribe()
        with patch("apps.api.events.event_bus", bus):
            await emit_rate_limit(wait_time=10)
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        d = msg["data"]
        assert d["attempt"] == 1
        assert d["max_retries"] == 3
        assert d["model"] == "auto"
