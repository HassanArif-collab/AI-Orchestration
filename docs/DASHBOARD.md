# Web Dashboard Documentation

The AI-Orchestration system includes a unified web dashboard built with FastAPI and vanilla JavaScript. This document provides comprehensive documentation for developers working with or extending the dashboard.

## Overview

The dashboard serves as the primary interface for:
- **Pipeline Management**: Create, monitor, and control video production runs
- **Human Gate Approval**: Review and approve/reject content at critical checkpoints
- **LLM Provider Configuration**: Manage FreeRouter providers (Groq, OpenRouter, Ollama)
- **Chat Interface**: Direct interaction with LLM models through FreeRouter
- **Memory Browser**: Inspect Zep Cloud agent memory and facts
- **Analytics Dashboard**: Monitor YouTube channel performance and competitor analysis
- **Visual Assets**: Manage visual asset manifests for video production
- **System Settings**: View configuration and health status

## Quick Start

### Starting the Dashboard

The dashboard requires two services running simultaneously:

**Terminal 1 - FreeRouter Proxy (port 4000)**
```bash
cd freerouter
python -m freerouter proxy
```

**Terminal 2 - Dashboard (port 3000)**
```bash
python -m apps.api.main
```

Access the dashboard at **http://localhost:3000**

### Why Two Services?

The architecture separates concerns:

1. **FreeRouter Proxy (port 4000)**: Handles all LLM API calls, manages API keys, provides automatic fallback between providers
2. **Dashboard (port 3000)**: Serves the web UI, handles pipeline state, proxies chat/provider requests to FreeRouter

This separation allows external tools (Claude Code, Cursor) to use the LLM proxy independently of the dashboard.

## Architecture

### Backend Structure

```
apps/api/
├── main.py              # FastAPI app, route registration, lifespan
├── events.py            # SSE event emitters for real-time updates
├── dependencies.py      # Shared clients (pipeline, memory, YouTube)
└── routers/
    ├── pipeline_routes.py   # Pipeline CRUD and human gates
    ├── provider_routes.py   # FreeRouter provider management
    ├── chat_routes.py       # Chat conversations (proxied)
    ├── memory_routes.py     # Zep Cloud memory browser
    ├── analytics_routes.py  # YouTube analytics
    ├── visual_routes.py     # Visual asset management
    └── settings_routes.py   # System configuration
```

### Frontend Structure

```
apps/api/static/
├── index.html           # Single-page app shell
├── css/
│   └── dashboard.css    # Dark theme styling
└── js/
    ├── app.js           # Navigation, SSE, utilities (loads first)
    ├── pipeline.js      # Pipeline tab functionality
    ├── chat.js          # Chat tab functionality
    ├── providers.js     # Providers tab functionality
    ├── memory.js        # Memory tab functionality
    ├── analytics.js     # Analytics tab functionality
    ├── visual.js        # Visual tab functionality
    └── settings.js      # Settings tab functionality
```

## API Endpoints

### Pipeline Routes (`/api/pipeline`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stages` | GET | Returns stage definitions and execution order |
| `/runs` | GET | List all pipeline runs (newest first) |
| `/runs` | POST | Create a new pipeline run |
| `/runs/{run_id}` | GET | Get full run details with stage outputs |
| `/runs/{run_id}` | DELETE | Delete a pipeline run |
| `/runs/{run_id}/approve` | POST | Approve current human gate |
| `/runs/{run_id}/reject` | POST | Reject with feedback |
| `/runs/{run_id}/feedback` | POST | Request feedback loop between stages |
| `/runs/{run_id}/output/{stage}` | GET | Get raw output for specific stage |

### Provider Routes (`/api/providers`)

These routes proxy to FreeRouter at port 4000.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Check provider health status |
| `/` | GET | List all configured providers |
| `/{provider}` | GET | Get specific provider details |

### Chat Routes (`/api/chat`)

These routes proxy to FreeRouter at port 4000.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/conversations` | GET | List all conversations |
| `/conversations` | POST | Create new conversation |
| `/conversations/{id}` | GET | Get conversation with messages |
| `/conversations/{id}/messages` | POST | Send message to conversation |
| `/conversations/{id}` | DELETE | Delete conversation |

### Memory Routes (`/api/memory`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sessions` | GET | List all Zep sessions |
| `/sessions/{session_id}` | GET | Get messages and facts for session |
| `/search` | POST | Semantic search across memory |
| `/facts/{session_id}` | GET | Get structured facts for session |

### Analytics Routes (`/api/analytics`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/channel` | GET | Get YouTube channel statistics |
| `/videos` | GET | Get recent videos from channel |
| `/competitors` | GET | Get competitor video analysis |
| `/snapshot` | POST | Save analytics snapshot |
| `/snapshots` | GET | List saved snapshots |

### Visual Routes (`/api/visual`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/manifest` | GET | Get visual asset manifest |
| `/manifest` | POST | Update asset manifest |
| `/assets` | GET | List all visual assets |
| `/assets/{asset_id}` | GET | Get specific asset details |

### Settings Routes (`/api/settings`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Get current configuration (secrets masked) |
| `/status` | GET | Get system component status |
| `/commands` | GET | Get startup command reference |

### SSE Events (`/api/events`)

Server-Sent Events endpoint for real-time updates.

**Event Types:**
- `pipeline_update`: Stage status change
- `stage_complete`: Stage finished successfully
- `human_gate`: Human approval required
- `pipeline_complete`: Full pipeline finished

## Frontend Development

### Tab System

The dashboard uses a hash-based tab navigation system:

```javascript
// Navigate to a tab
window.location.hash = 'pipeline';  // Goes to Pipeline tab
window.location.hash = 'chat';      // Goes to Chat tab

// Each tab has an init and refresh function
const TAB_INITS = {
  pipeline:  () => initPipeline(),
  chat:      () => initChat(),
  // ...
};

const TAB_REFRESH = {
  pipeline:  () => refreshPipeline(),
  chat:      () => {},
  // ...
};
```

### API Helper

All API calls use the `api()` helper function defined in `app.js`:

```javascript
// GET request
const runs = await api('/api/pipeline/runs');

// POST request
const result = await api('/api/pipeline/runs', {
  method: 'POST',
  body: { topic: 'My Topic' }
});

// DELETE request
await api(`/api/pipeline/runs/${runId}`, { method: 'DELETE' });
```

### Toast Notifications

Use `showToast()` for user feedback:

```javascript
showToast('Pipeline started', 'info');      // Blue info toast
showToast('Stage complete!', 'success');    // Green success toast
showToast('Action needed', 'warning');      // Yellow warning toast
showToast('Error occurred', 'error');       // Red error toast
```

### Modal Dialogs

Use `showModal()` and `hideModal()` for modal interactions:

```javascript
// Show modal with HTML content
showModal(`
  <h2>Confirm Action</h2>
  <p>Are you sure you want to proceed?</p>
  <button class="btn btn-primary" onclick="confirmAction()">Confirm</button>
  <button class="btn btn-outline" onclick="hideModal()">Cancel</button>
`);

// Hide modal
hideModal();
```

### SSE Connection

The dashboard maintains a persistent SSE connection:

```javascript
// Connection is established automatically on load
// Events are dispatched in app.js

// Listen for specific events
_es.addEventListener('pipeline_update', (e) => {
  const data = JSON.parse(e.data);
  // Handle update
});

_es.addEventListener('human_gate', (e) => {
  const data = JSON.parse(e.data);
  showToast(`Action needed: ${data.stage}`, 'warning');
});
```

## Pipeline Stages

The pipeline has 9 stages with dependencies and feedback targets:

```
trend_analysis → human_topic_approval → research → script_writing
                                              ↓
                                    visual_planning (parallel with seo)
                                              ↓
                                        human_review
                                              ↓
                                       asset_creation
                                              ↓
                                           publish
```

### Stage Definitions

| Stage | Type | Dependencies | Feedback Targets |
|-------|------|--------------|------------------|
| `trend_analysis` | Auto | None | - |
| `human_topic_approval` | Human Gate | `trend_analysis` | - |
| `research` | Auto | `human_topic_approval` | - |
| `script_writing` | Auto | `research` | `research` |
| `visual_planning` | Auto | `script_writing` | `script_writing` |
| `seo` | Auto | `script_writing` | - |
| `human_review` | Human Gate | `visual_planning`, `seo` | - |
| `asset_creation` | Auto | `human_review` | - |
| `publish` | Auto | `asset_creation` | - |

### Human Gates

Human gates pause the pipeline for user approval:

1. **human_topic_approval**: Select from trending topics
2. **human_review**: Review script and visual plan before production

## Styling

The dashboard uses a dark theme with teal accent color:

### CSS Variables

```css
:root {
  --bg-primary:      #0d0d0d;   /* Main background */
  --bg-secondary:    #141414;   /* Cards, sidebar */
  --bg-tertiary:     #1e1e1e;   /* Input fields */
  --accent-primary:  #1D9E75;   /* Teal accent */
  --accent-success:  #1D9E75;   /* Green for success */
  --accent-warning:  #BA7517;   /* Yellow for warnings */
  --accent-error:    #A32D2D;   /* Red for errors */
  --sidebar-width:   220px;
}
```

### Status Dots

```html
<span class="status-dot online"></span>    <!-- Green -->
<span class="status-dot warning"></span>   <!-- Yellow -->
<span class="status-dot offline"></span>   <!-- Red -->
<span class="status-dot running"></span>   <!-- Blue, animated -->
<span class="status-dot pending"></span>   <!-- Gray -->
```

### Buttons

```html
<button class="btn btn-primary">Primary</button>
<button class="btn btn-success">Success</button>
<button class="btn btn-danger">Danger</button>
<button class="btn btn-info">Info</button>
<button class="btn btn-outline">Outline</button>
<button class="btn btn-sm btn-primary">Small</button>
```

## Dependencies

### Backend Dependencies

- **FastAPI**: Web framework
- **Uvicorn**: ASGI server
- **Pydantic**: Request/response models
- **aiohttp**: Async HTTP client for FreeRouter proxy

### Frontend Dependencies

- **No build step required**: Vanilla JavaScript
- **No external libraries**: All functionality built-in
- **Browser APIs**: Fetch, EventSource, localStorage

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | Yes* | - | Groq LLM provider key |
| `OPENROUTER_API_KEY` | No | - | OpenRouter models access |
| `ZEP_API_KEY` | No | - | Zep Cloud memory storage |
| `YOUTUBE_API_KEY` | No | - | YouTube Data API |
| `NOTION_API_KEY` | No | - | Notion integration |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

*At least one LLM provider key is required in `freerouter/.env`

### Ports

| Service | Port | Purpose |
|---------|------|---------|
| Dashboard | 3000 | Web UI and API |
| FreeRouter Proxy | 4000 | LLM API proxy |
| FreeRouter Web | 8080 | Standalone FreeRouter dashboard (optional) |

## Troubleshooting

### Dashboard Won't Start

1. Check if port 3000 is available
2. Verify `pip install -e ".[all]"` completed successfully
3. Check for import errors in the console

### FreeRouter Connection Failed

1. Ensure FreeRouter is running: `python -m freerouter proxy`
2. Check `freerouter/.env` has at least one API key
3. Verify port 4000 is accessible

### Pipeline Stuck at Human Gate

1. Check the Pipeline tab for the waiting run
2. Click on the run card to open the approval modal
3. Select an option and approve

### Memory Tab Empty

1. Verify `ZEP_API_KEY` is set in `.env`
2. Check if any pipeline runs have been executed
3. Zep sessions are created on first pipeline run

### SSE Not Working

1. Check browser console for EventSource errors
2. Verify `/api/events` endpoint is accessible
3. Check for CORS issues if accessing from different origin

## Extending the Dashboard

### Adding a New Tab

1. Add navigation link in `index.html`:
```html
<li><a href="#newtab" class="nav-link" data-tab="newtab">
  <span class="nav-icon">🆕</span>
  <span class="nav-label">New Tab</span>
</a></li>
```

2. Add content div in `index.html`:
```html
<div id="tab-newtab" class="tab-content"></div>
```

3. Create `static/js/newtab.js`:
```javascript
function initNewtab() {
  const container = document.getElementById('tab-newtab');
  container.innerHTML = '<div class="card">...</div>';
  refreshNewtab();
}

function refreshNewtab() {
  // Fetch data and update UI
}
```

4. Register in `app.js`:
```javascript
const TAB_INITS = {
  // ...
  newtab: () => initNewtab(),
};

const TAB_REFRESH = {
  // ...
  newtab: () => refreshNewtab(),
};
```

5. Include script in `index.html`:
```html
<script src="/js/newtab.js"></script>
```

### Adding a New API Route

1. Create router file in `routers/new_routes.py`:
```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_new_data():
    return {"data": "example"}
```

2. Register in `main.py`:
```python
from apps.api.routers import new_routes

app.include_router(new_routes.router, prefix="/api/new", tags=["new"])
```

## Best Practices

1. **Always handle missing dependencies gracefully**: The dashboard should render something useful even when optional services (Zep, YouTube) are not configured.

2. **Use SSE for real-time updates**: Prefer SSE over polling for pipeline status updates.

3. **Mask sensitive data in API responses**: Never expose API keys in settings responses.

4. **Provide helpful error messages**: When a service is unavailable, explain what the user needs to configure.

5. **Use semantic HTML**: Proper heading hierarchy, ARIA labels for accessibility.

6. **Maintain responsive design**: Test on mobile viewports (sidebar collapses at 768px).
