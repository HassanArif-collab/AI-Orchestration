# Kanban Pipeline Dashboard - Implementation Handoff

## 🎯 Task Overview

We are implementing a **Kanban-style Command Center** for the YouTube Pipeline system. The dashboard should show a visual board with 6 columns representing pipeline stages, where tasks (pipeline runs) can be dragged between columns, color-coded by topic finder instance, and show real-time agent activity.

---

## 📋 Requirements

### User Story
As a pipeline operator, I want to:
1. See all pipeline runs in a Kanban board view
2. Create new "Topic Finding" sessions that spawn suggested topics
3. Drag tasks between stages (Topic Finding → Suggested Topics → Researching → Script → Visual → Notion)
4. Click any task to see a detailed view showing:
   - Current stage output (research, script, visual cues)
   - Real-time agent monologue/thoughts (SSE stream)
   - Notion publication link when complete
5. See color-coding: Topic Finder cards have a color; all topics they generate inherit that color
6. See stage-based theming: The detail drawer's accent color changes based on the task's current stage
7. Watch tasks automatically move between stages as agents work (back-and-forth between script/research/visual if needed)

---

## ✅ What Has Been Implemented

### 1. Database Layer
**File:** `freerouter/src/freerouter/storage.py`

Added `pipeline_tasks` table with these columns:
- `id` (TEXT PRIMARY KEY)
- `parent_id` (TEXT) - for color inheritance
- `title` (TEXT) - task title
- `stage` (INTEGER) - 1-6 representing the 6 columns
- `status` (TEXT) - idle, thinking, error, etc.
- `color` (TEXT) - hex color for visual identification
- `content` (TEXT) - general content
- `research` (TEXT) - research output
- `script` (TEXT) - script content
- `visual_cues` (TEXT) - visual planning output
- `notion_url` (TEXT) - published Notion link
- `thoughts` (TEXT) - JSON array of agent thoughts
- `updated_at` (TEXT) - timestamp

**Functions added:**
- `create_pipeline_task(title, stage, parent_id, color)` → creates task with UUID
- `list_pipeline_tasks()` → returns all tasks ordered by updated_at
- `get_pipeline_task(tid)` → returns single task or None
- `update_pipeline_task(tid, updates)` → updates any fields
- `delete_pipeline_task(tid)` → removes task
- `add_task_thought(tid, thought)` → appends to thoughts array (keeps last 50)

---

### 2. Backend API (FastAPI)
**File:** `freerouter/src/freerouter/web/app.py`

**Pydantic Models:**
- `PipelineTaskCreate` - title, stage, parent_id, color
- `PipelineTaskUpdate` - optional fields for partial updates
- `PipelineEvent` - task_id, event_type, data (for agent reporting)

**Endpoints:**
- `GET /api/pipeline/tasks` - list all tasks
- `POST /api/pipeline/tasks` - create new task
- `PATCH /api/pipeline/tasks/{tid}` - update task
- `DELETE /api/pipeline/tasks/{tid}` - delete task
- `POST /api/pipeline/events` - **CRITICAL**: agents use this to report progress
  - `event_type` can be: `thought`, `stage_change`, `status_change`, `artifact`
- `GET /api/pipeline/stream` - SSE endpoint for real-time UI updates

**Real-time System:**
- Global `pipeline_subscribers` list holds asyncio.Queues for each connected client
- `broadcast_pipeline_event(event)` sends updates to all connected browsers
- Events are broadcast when tasks are created/updated/deleted

---

### 3. Frontend HTML Structure
**File:** `freerouter/src/freerouter/web/static/index.html`

**Added:**
- Pipeline tab button in navigation (line 21)
- Pipeline tab panel (lines 37-90) with 6 columns:
  1. Topic Finding (data-stage="1") - has "+ Add" button
  2. Suggested Topics (data-stage="2")
  3. Researching (data-stage="3")
  4. Script (data-stage="4")
  5. Visual (data-stage="5")
  6. Notion (data-stage="6")

**Task Detail Drawer** (lines 95-135):
- Slides in from right when task card clicked
- Shows: title, status, ID, stage badge
- Artifact box (displays research/script/visual based on stage)
- Notion link section (if task.notion_url exists)
- Agent thoughts log (scrollable terminal-like view)

---

### 4. Frontend CSS
**File:** `freerouter/src/freerouter/web/static/css/styles.css`

**Kanban Styles** (lines 231-321):
- `.pipeline-container` - horizontal scroll wrapper
- `.kanban-board` - flex container for columns
- `.kanban-column` - fixed width (280px), gray background
- `.task-card` - white card with left border color (dynamic)
- `.task-card.active` - pulsing border for "thinking" status
- `.task-title` - 2-line truncation
- `.task-meta` - status and timestamp

**Drawer Styles** (lines 365-463):
- `.drawer` - fixed full-height right panel
- `.drawer-content` - inner container with stage-based top border color
- `.stage-1` through `.stage-6` - different border colors for each stage
- `.artifact-box` - scrollable output display
- `.thought-log` - dark terminal-style monologue view
- `.thought-item` - individual thought entries with timestamp

---

### 5. Frontend JavaScript
**File:** `freerouter/src/freerouter/web/static/js/pipeline.js`

**Pipeline Object:**
- `tasks: []` - array of task objects
- `activeTaskId` - currently open task in drawer
- `eventSource` - SSE connection

**Key Methods:**
- `init()` - fetch tasks, render board, setup listeners, SSE, drag-drop
- `fetchTasks()` - GET /api/pipeline/tasks
- `renderBoard()` - clears all columns, re-renders task cards
- `createTaskCard(task)` - creates draggable card with color border
- `setupDragAndDrop()` - enables drag-drop between columns
- `moveTask(taskId, newStage)` - PATCH /api/pipeline/tasks/{id} with {stage}
- `openDrawer(taskId)` - shows detail panel, sets stage class
- `updateDrawer(task)` - updates all drawer content
- `appendThought(thought)` - adds thought to monologue log
- `closeDrawer()` - hides panel

**SSE Handling:**
- Connects to `/api/pipeline/stream`
- Event types: `task_created`, `task_updated`, `task_deleted`, `agent_event`
- Auto-refreshes board on changes
- Updates drawer if active task changed

---

### 6. App Integration
**File:** `freerouter/src/freerouter/web/static/js/app.js`

Modified to include pipeline tab:
- `setupTabs()` now handles 'pipeline' tab
- Calls `Pipeline.init()` when pipeline tab activated

---

### 7. Bug Fix: PipelineRun.from_dict
**File:** `packages/pipeline/state.py`

**Problem:** The `from_dict` classmethod was incorrectly placed outside the `PipelineRun` class (at module level), causing `AttributeError: type object 'PipelineRun' has no attribute 'from_dict'`.

**Fix:** Moved `from_dict` inside the `PipelineRun` class (lines 180-199) with proper indentation.

---

## 🔌 Integration Points (What's Missing)

The Kanban UI is **fully functional but isolated**. It needs to connect to the actual pipeline agents. Here's what needs to be done:

### 1. Agent Event Bridge

**Where:** Create a new module `packages/agents/kanban_callback.py` or add to `packages/agents/base.py`

**Purpose:** Whenever a CrewAI agent thinks or acts, it should report to the Kanban dashboard.

**Implementation:**
```python
class KanbanCallbackHandler:
    """Bridge between CrewAI agents and the Kanban dashboard."""
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.client = RouterClient()  # or use httpx directly
    
    async def on_thought(self, thought: str):
        """Called when agent generates a thought."""
        await self.client.post('/api/pipeline/events', json={
            'task_id': self.task_id,
            'event_type': 'thought',
            'data': {'content': thought}
        })
    
    async def on_stage_change(self, stage: int):
        """Called when task moves to new stage."""
        await self.client.post('/api/pipeline/events', json={
            'task_id': self.task_id,
            'event_type': 'stage_change',
            'data': {'stage': stage}
        })
    
    async def on_status_change(self, status: str):
        """Called when status changes (idle → thinking → error)."""
        await self.client.post('/api/pipeline/events', json={
            'task_id': self.task_id,
            'event_type': 'status_change',
            'data': {'status': status}
        })
    
    async def on_artifact(self, key: str, value: str):
        """Called when agent produces output (research, script, etc.)."""
        await self.client.post('/api/pipeline/events', json={
            'task_id': self.task_id,
            'event_type': 'artifact',
            'data': {'key': key, 'value': value}
        })
```

**Usage in agents:**
- In `packages/content_factory/topic_finder/finder.py` - when topic finder starts, create a task and pass handler
- In `packages/content_factory/production/deep_research.py` - report thoughts and research output
- In `packages/content_factory/script_generator/evolution_loop.py` - report script drafts
- In `packages/content_factory/music/agent.py` - report visual cues

---

### 2. Pipeline Runner Integration

**File:** `apps/api/routers/pipeline_routes.py`

**Function:** `_run_pipeline_bg(run_id)` (lines 101-149)

**What to add:**
1. At start of pipeline run, create a Kanban task:
   ```python
   # Create a task for this pipeline run
   task_resp = await client.post('/api/pipeline/tasks', json={
       'title': f"Pipeline: {run_id[:8]}",
       'stage': 1,  # Start at Topic Finding
       'color': '#0066cc'  # Or generate random
   })
   task_id = task_resp['id']
   # Store task_id in run state: run.set_output('kanban_task_id', task_id)
   ```

2. When each stage completes, update the task:
   ```python
   # After stage execution
   await client.post('/api/pipeline/events', json={
       'task_id': task_id,
       'event_type': 'stage_change',
       'data': {'stage': STAGE_NUMBER}
   })
   ```

3. Map pipeline stages to Kanban stages:
   - Trend Analysis (1) → Topic Finding (1) - but we auto-create topics
   - Human Topic Approval → Suggested Topics (2) - topics appear here
   - Research (3) → Researching (3)
   - Script Writing (4) → Script (4)
   - Visual Planning (5) → Visual (5)
   - SEO (parallel) → also goes to Script or Visual?
   - Human Review → stays in current stage
   - Asset Creation → Notion (6)
   - Publish → Notion (6) with notion_url

4. When Notion publishes, update task with URL:
   ```python
   await client.post('/api/pipeline/events', json={
       'task_id': task_id,
       'event_type': 'artifact',
       'data': {'key': 'notion_url', 'value': notion_url}
   })
   ```

---

### 3. Topic Finder → Suggested Topics Flow

**Current gap:** The "+ Add" button in Topic Finding column creates a generic task. It should actually spawn a Topic Finder agent run.

**Desired flow:**
1. User clicks "+ Add" in Topic Finding column
2. Modal asks for initial prompt/trend to analyze
3. System creates a task with `status: thinking` and `stage: 1`
4. System spawns a `TopicFinderAgent` (from `packages/content_factory/topic_finder/finder.py`)
5. As the agent discovers topics, it:
   - Creates child tasks in Suggested Topics column (stage 2) with `parent_id` set to the Topic Finder task
   - Each child inherits the parent's color
   - Reports thoughts to parent task's monologue
6. When Topic Finder completes, parent task status becomes `idle`

**Implementation:**
- Modify `Pipeline.createTask()` in `pipeline.js` to accept a prompt
- POST to `/api/pipeline/tasks` with title and stage=1
- Backend should trigger a background task that runs the TopicFinderAgent
- TopicFinderAgent should call back to create suggested topic tasks

---

### 4. Color Inheritance

**Requirement:** When a Topic Finder (stage 1) creates Suggested Topics (stage 2), they must have the same left-border color.

**Implementation:**
- When creating a child task, pass `parent_id` and `color` from parent
- In `create_pipeline_task()` in storage.py, if `color` not provided, generate random
- In frontend `renderBoard()`, group tasks by parent_id and assign colors? Actually simpler: each task stores its own color; parent passes it to children.

---

### 5. Stage-Based Drawer Theming

**Already implemented in CSS** (lines 457-463):
```css
.drawer-content.stage-1 { border-top: 6px solid #0066cc; }
.drawer-content.stage-2 { border-top: 6px solid #2da44e; }
...
```

**In `pipeline.js`** `openDrawer()` (line 207):
```javascript
content.className = 'drawer-content';
content.classList.add(`stage-${task.stage}`);
```

This already works! Just need to ensure task.stage updates correctly.

---

### 6. Back-and-Forth Stage Jumps

**Requirement:** If Script Writer determines research is incomplete, task should automatically move back to Researching stage.

**Implementation:**
- Agents can report `stage_change` events at any time
- When a task's stage changes via PATCH, the frontend automatically re-renders the board (card moves to new column)
- The drawer (if open) updates its stage class and content

**No additional work needed** - this is already built into the SSE system.

---

## 🧪 Testing Checklist

Once integration is complete, verify:

1. **Kanban board loads** with 6 columns
2. **Add button** in Topic Finding creates a new task
3. **Drag-and-drop** moves tasks between columns (PATCH request sent)
4. **Task card** shows title, status, time, and colored left border
5. **Clicking card** opens drawer with correct stage color
6. **SSE updates** - when task updated in another browser, both update in real-time
7. **Thoughts appear** in drawer monologue as agents think
8. **Artifacts display** - research, script, visual cues appear in appropriate stages
9. **Notion link** shows when task reaches stage 6 with notion_url
10. **Color inheritance** - child tasks have same color as parent
11. **Stage transitions** - task moves automatically when agent reports stage change
12. **Back-and-forth** - task can move from Script back to Research if needed

---

## 📁 Key Files Reference

### Backend
- `freerouter/src/freerouter/storage.py` - database CRUD for pipeline_tasks
- `freerouter/src/freerouter/web/app.py` - API endpoints and SSE
- `apps/api/routers/pipeline_routes.py` - existing pipeline runner (needs integration)

### Frontend
- `freerouter/src/freerouter/web/static/index.html` - HTML structure
- `freerouter/src/freerouter/web/static/css/styles.css` - Kanban + Drawer styles
- `freerouter/src/freerouter/web/static/js/pipeline.js` - Kanban logic
- `freerouter/src/freerouter/web/static/js/app.js` - tab management

### Pipeline Core
- `packages/pipeline/state.py` - PipelineRun class (fixed from_dict)
- `packages/pipeline/runner.py` - PipelineRunner (background execution)
- `packages/pipeline/stages.py` - Stage enum and dependencies

### Agents (need callback integration)
- `packages/content_factory/topic_finder/finder.py`
- `packages/content_factory/production/deep_research.py`
- `packages/content_factory/script_generator/evolution_loop.py`
- `packages/content_factory/music/agent.py`

---

## 🚀 Next Steps for Integration

1. **Create KanbanCallbackHandler** in a new file or in `packages/agents/base.py`
2. **Modify TopicFinderAgent** to:
   - Accept a `task_id` and `callback` parameter
   - Create a Kanban task when started
   - For each discovered topic, create a child task in stage 2
   - Report thoughts via callback
3. **Modify PipelineRunner** (`_run_pipeline_bg`) to:
   - Create a Kanban task at start
   - Store `task_id` in run state
   - Report stage changes and artifacts via `/api/pipeline/events`
4. **Modify Research, Script, Visual agents** to report progress via callback
5. **Test end-to-end** with a full pipeline run

---

## 📝 Notes

- The current implementation is **UI-only**; it works with manual task creation and updates
- The SSE system is fully functional and tested
- The database schema supports all required fields
- Drag-and-drop uses native HTML5 API (no external libraries)
- The drawer shows real-time thoughts as they arrive via SSE
- Stage colors are defined in CSS and applied dynamically

---

## 🔧 Quick Start for Testing

1. Start the API: `python -m apps.api.main` (port 3000)
2. Open http://localhost:3000
3. Click "Pipeline" tab
4. Click "+ Add" in Topic Finding column
5. Enter a title (e.g., "Test Topic")
6. A task card appears
7. Click the card to open drawer
8. Drag card to other columns
9. Open browser console to see SSE events

---

**That's the complete state! The Kanban board is built and ready - just needs agent integration.**