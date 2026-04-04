# API Reference

## Overview

All endpoints are prefixed with `/api`. The API serves the web dashboard and supports programmatic access.

### Base URL
```
http://localhost:3000/api
```

### Why REST + SSE?

We use REST for CRUD operations and Server-Sent Events (SSE) for real-time updates.

**Reasoning**:
- REST is familiar and well-supported
- SSE provides push notifications without WebSocket complexity
- SSE has native browser support (`EventSource` API)
- We only need server → client updates (one-way is sufficient)

---

## Pipeline Endpoints

### GET /pipeline/stages

Get the pipeline stage definitions.

**Why this exists**: Dashboard needs to render stage graph before any run exists.

**Response**:
```json
{
  "stages": [
    {"name": "trend_analysis", "label": "Trend Analysis", "is_human_gate": false, "dependencies": []},
    {"name": "human_topic_approval", "label": "Pick Topic", "is_human_gate": true, "dependencies": ["trend_analysis"]},
    ...
  ],
  "execution_order": ["trend_analysis", "human_topic_approval", ...],
  "parallel_stages": [["visual_planning", "seo"]]
}
```

---

### GET /pipeline/runs

List all pipeline runs.

**Why this exists**: Dashboard needs to show run history. Returns newest first.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Max runs to return |

**Response**:
```json
[
  {
    "run_id": "uuid-here",
    "current_stage": "human_review",
    "status": "waiting_human",
    "video_title": "Why Pakistan's Economy...",
    "created_at": "2025-03-28T10:00:00Z",
    "updated_at": "2025-03-28T10:15:00Z",
    "stages": {
      "trend_analysis": {"status": "complete", "output": [...]},
      "research": {"status": "complete", "output": {...}},
      ...
    }
  }
]
```

---

### POST /pipeline/runs

Create a new pipeline run.

**Why this exists**: Starts pipeline execution. Returns immediately with run_id; pipeline runs in background.

**Request Body**:
```json
{
  "topic": "Optional seed topic"
}
```

**Response**:
```json
{
  "run_id": "uuid-here",
  "status": "started"
}
```

---

### GET /pipeline/runs/{run_id}

Get full details of a specific run.

**Why this exists**: Dashboard polls this during execution to show progress.

**Response**: Same structure as list item, with full `stages` object.

---

### DELETE /pipeline/runs/{run_id}

Delete a pipeline run.

**Why this exists**: Clean up test runs or cancelled runs.

**Response**:
```json
{
  "deleted": "run-id-here"
}
```

---

### POST /pipeline/runs/{run_id}/approve

Approve a human gate and continue pipeline.

**Why this exists**: Human gates pause pipeline. This endpoint resumes execution.

**Request Body**:
```json
{
  "selection": {"topic_statement": "The topic I chose"},
  "feedback": "Optional feedback"
}
```

**Response**: Updated run object.

---

### POST /pipeline/runs/{run_id}/reject

Reject at a human gate with feedback.

**Why this exists**: Send pipeline back for revision instead of approving.

**Request Body**:
```json
{
  "feedback": "This needs more research on X"
}
```

**Response**: Updated run object with status back to "running".

---

### GET /pipeline/runs/{run_id}/iterations

Get iteration history from the evaluation loop.

**Why this exists**: Shows how the script improved over iterations (A-B testing).

**Response**:
```json
{
  "run_id": "uuid-here",
  "iterations": [
    {"iteration": 1, "score": 72.5, "mutations": [...]},
    {"iteration": 2, "score": 78.0, "mutations": [...]},
    {"iteration": 3, "score": 85.2, "mutations": [...]}
  ]
}
```

---

### GET /pipeline/runs/resumable

List runs that can be resumed (error or waiting_human states).

**Why this exists**: Dashboard shows crashed runs that need attention.

---

### POST /pipeline/runs/{run_id}/resume

Resume a crashed or paused run.

**Why this exists**: Recover from failures without starting over.

---

## Kanban Endpoints

### GET /kanban/tasks

List all Kanban tasks.

**Why this exists**: Kanban board shows pipeline progress visually.

**Query Parameters**:
| Param | Type | Description |
|-------|------|-------------|
| `stage` | int | Filter by column (1-6) |
| `status` | string | Filter by status |

---

### POST /kanban/tasks

Create a Kanban task.

**Why this exists**: Manual task creation for non-pipeline work.

**Request Body**:
```json
{
  "title": "Task title",
  "stage": 1,
  "parent_id": "optional-parent-uuid"
}
```

---

### PATCH /kanban/tasks/{task_id}

Update a Kanban task.

**Request Body**:
```json
{
  "stage": 3,
  "status": "thinking"
}
```

---

### POST /kanban/events

Report an agent event (thought, stage change, artifact).

**Why this exists**: Agents report progress without HTTP self-calls.

**Request Body**:
```json
{
  "task_id": "uuid",
  "event_type": "thought",
  "data": {"content": "I'm analyzing the research..."}
}
```

---

## Chat Endpoints

### GET /chat/conversations

List chat conversations.

**Why this exists**: Browse past conversations for reference.

---

### POST /chat/conversations

Create a new conversation.

**Request Body**:
```json
{
  "provider": "groq",
  "model": "llama-3.3-70b-versatile"
}
```

---

### POST /chat/conversations/{id}/messages

Send a message in a conversation.

**Request Body**:
```json
{
  "role": "user",
  "content": "Hello, how are you?"
}
```

---

## Provider Endpoints

### GET /providers/health

Check LLM provider status.

**Why this exists**: Dashboard shows which providers are available.

**Response**:
```json
{
  "providers": [
    {"name": "groq", "status": "healthy", "latency_ms": 45},
    {"name": "openrouter", "status": "healthy", "latency_ms": 120},
    {"name": "ollama", "status": "unhealthy", "error": "Connection refused"}
  ]
}
```

---

## Memory Endpoints

### GET /memory/sessions

List Zep Cloud memory sessions.

**Why this exists**: Browse agent memory for debugging.

---

### GET /memory/sessions/{session_id}

Get memory for a specific session.

**Response**:
```json
{
  "session_id": "uuid",
  "facts": ["User prefers technical content", "Previous topic was about AI"],
  "messages": [...]
}
```

---

## Analytics Endpoints

### GET /analytics/channel

Get YouTube channel analytics.

**Why this exists**: Dashboard shows channel performance.

**Query Parameters**:
| Param | Type | Description |
|-------|------|-------------|
| `channel_id` | string | YouTube channel ID |
| `days` | int | Days of history (default: 30) |

---

## Events Endpoint (SSE)

### GET /events

Server-Sent Events stream for real-time updates.

**Why this exists**: Push notifications without polling.

**Event Types**:
| Event | Data |
|-------|------|
| `pipeline_update` | `{run_id, stage, status}` |
| `stage_complete` | `{run_id, stage, output}` |
| `human_gate` | `{run_id, stage}` |
| `pipeline_complete` | `{run_id}` |
| `agent_event` | `{task_id, event_type, data}` |

**Usage**:
```javascript
const source = new EventSource('/api/events');
source.addEventListener('human_gate', (event) => {
  const data = JSON.parse(event.data);
  showNotification(`Human gate at ${data.stage}`);
});
```

---

## Health Endpoints

### GET /health

Basic health check.

**Response**:
```json
{
  "status": "healthy",
  "version": "0.5.0"
}
```

---

### GET /health/ready

Readiness check (all dependencies available).

**Response**:
```json
{
  "status": "ready",
  "checks": {
    "freerouter": "healthy",
    "database": "healthy"
  }
}
```

---

## Error Responses

All endpoints return consistent error format:

```json
{
  "detail": "Error message here"
}
```

**Common HTTP Status Codes**:
| Code | Meaning |
|------|---------|
| 400 | Bad request (validation error) |
| 404 | Resource not found |
| 500 | Internal server error |
| 503 | Service unavailable (dependency down) |

---

## Rate Limits

Currently no rate limiting on API endpoints. LLM rate limits are handled by FreeRouter.

---

## Authentication

Currently no authentication. For production deployment, add:
1. API key header (`X-API-Key`)
2. Or OAuth2/JWT for user sessions

---

## OpenAPI Schema

Full schema available at:
```
http://localhost:3000/openapi.json
```

Interactive docs at:
```
http://localhost:3000/docs
```
