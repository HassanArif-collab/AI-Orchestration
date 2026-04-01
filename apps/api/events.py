"""
events.py — Server-Sent Events bus for real-time dashboard updates.

The EventBus broadcasts to all connected SSE clients. Routers call the
emit_* helpers when pipeline stages change, providers rate-limit, etc.

Frontend connects with: new EventSource('/api/events')
"""

from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone
from fastapi import Request
from fastapi.responses import StreamingResponse


class EventBus:
    """In-memory event bus. Broadcasts to all SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def publish(self, event_type: str, data: dict) -> None:
        """Broadcast an event to all subscribers."""
        msg = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)


# Global singleton
event_bus = EventBus()


async def sse_endpoint(request: Request) -> StreamingResponse:
    """SSE endpoint. Frontend connects with EventSource('/api/events')."""

    async def generate():
        q = event_bus.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"event: {msg['type']}\ndata: {json.dumps(msg)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            event_bus.unsubscribe(q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ─── Convenience emitters ─────────────────────────────────────────────────────

async def emit_pipeline_update(run_id: str, stage: str, status: str) -> None:
    await event_bus.publish("pipeline_update",
                            {"run_id": run_id, "stage": stage, "status": status})


async def emit_stage_complete(run_id: str, stage: str, summary: str = "") -> None:
    await event_bus.publish("stage_complete",
                            {"run_id": run_id, "stage": stage, "summary": summary})


async def emit_human_gate(run_id: str, stage: str) -> None:
    await event_bus.publish("human_gate", {"run_id": run_id, "stage": stage})


async def emit_pipeline_complete(run_id: str) -> None:
    await event_bus.publish("pipeline_complete", {"run_id": run_id})


async def emit_provider_status(provider: str, status: str) -> None:
    await event_bus.publish("provider_status",
                            {"provider": provider, "status": status})


async def emit_iteration_complete(
    run_id: str,
    iteration: int,
    score: float,
    previous_score: float,
    mutation_zone: str,
    beat_baseline: bool,
    script_json: dict | None = None,
) -> None:
    """Emit an SSE event when an ExperimentLoop iteration completes.
    
    This feeds the frontend score graph and provides real-time feedback
    on script evolution progress.
    
    Args:
        run_id: Pipeline run ID
        iteration: Iteration number (0-indexed)
        score: Current iteration score
        previous_score: Score before this iteration
        mutation_zone: Which mutation zone was applied
        beat_baseline: Whether this iteration beat the baseline
        script_json: Full script snapshot for live graph point clicks
    """
    await event_bus.publish("iteration_complete", {
        "run_id": run_id,
        "iteration": iteration,
        "score": round(score, 1),
        "previous_score": round(previous_score, 1),
        "delta": round(score - previous_score, 1),
        "mutation_zone": mutation_zone,
        "beat_baseline": beat_baseline,
        "script_json": script_json,
    })


async def emit_task_created(task_data: dict) -> None:
    """Emit a 'task_created' event for the Kanban board."""
    await event_bus.publish("task_created", task_data)


async def emit_rate_limit(
    wait_time: int,
    attempt: int = 1,
    max_retries: int = 3,
    model: str = "auto",
) -> None:
    """Emit a 'rate_limit' SSE event when an LLM provider rate-limits us.

    The frontend can use this to show a progress indicator or toast
    telling the user the system is waiting before retrying.

    Args:
        wait_time: Seconds until the next retry
        attempt: Current retry attempt number (1-indexed)
        max_retries: Maximum number of retries configured
        model: The model that was being called
    """
    await event_bus.publish("rate_limit", {
        "wait_time": wait_time,
        "attempt": attempt,
        "max_retries": max_retries,
        "model": model,
    })
