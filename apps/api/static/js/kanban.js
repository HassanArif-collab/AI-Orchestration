/**
 * kanban.js — Kanban board management for YouTube Pipeline.
 * 
 * Refactored to be a direct view of PipelineRunner runs.
 */

// Stage labels and configuration
const KANBAN_STAGES = {
    1: { name: 'Topic Finding', icon: '🔍', color: '#0066cc' },
    2: { name: 'Suggested Topics', icon: '💡', color: '#2da44e' },
    3: { name: 'Researching', icon: '📚', color: '#8a63d2' },
    4: { name: 'Script', icon: '✍️', color: '#d4a017' },
    5: { name: 'Visual', icon: '🎨', color: '#d1242f' },
    6: { name: 'Notion', icon: '📄', color: '#0969da' }
};

// Status styles
const STATUS_STYLES = {
    idle: 'status-idle',
    thinking: 'status-thinking',
    error: 'status-error',
    complete: 'status-complete',
    waiting: 'status-waiting'
};

// Module state
const Kanban = {
    tasks: [],
    activeTaskId: null,
    initialized: false,
    
    async init() {
        if (this.initialized) {
            await this.refresh();
            return;
        }
        
        const container = document.getElementById('tab-kanban');
        if (!container) return;
        
        container.innerHTML = this._getBoardHTML();
        
        // Render cached data immediately (from SSE events while on other tabs)
        // This ensures the board shows instantly without waiting for API
        if (this.tasks && this.tasks.length > 0) {
            this._renderBoard();
        }
        
        // Then fetch fresh data in background
        await this.refresh();
        this._setupEventListeners();
        this._setupDragAndDrop();
        this.initialized = true;
    },
    
    _getBoardHTML() {
        return `
            <div class="kanban-header">
                <h2 class="kanban-title">Content Pipeline</h2>
                <div class="kanban-actions">
                    <button class="btn btn-primary btn-sm" onclick="Kanban.createTask()">
                        + New Topic
                    </button>
                    <button class="btn btn-outline btn-sm" onclick="Kanban.refresh()">
                        🔄 Refresh
                    </button>
                </div>
            </div>
            <div class="kanban-container">
                <div class="kanban-board" id="kanban-board">
                    ${Object.entries(KANBAN_STAGES).map(([stage, config]) => `
                        <div class="kanban-column" data-stage="${stage}">
                            <div class="column-header">
                                <span class="column-icon">${config.icon}</span>
                                <span class="column-title">${config.name}</span>
                                <span class="column-count" id="count-${stage}">0</span>
                            </div>
                            <div class="task-list" id="stage-${stage}"></div>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <!-- Task Detail Drawer -->
            <div id="kanban-drawer" class="kanban-drawer hidden" style="display: none;">
                <div class="drawer-overlay" onclick="Kanban.closeDrawer()"></div>
                <div class="drawer-content" id="drawer-content">
                    <div class="drawer-header">
                        <button class="drawer-close" onclick="Kanban.closeDrawer()">×</button>
                        <h2 id="drawer-title">Task Title</h2>
                        <div class="drawer-meta">
                            <span id="drawer-status" class="task-status-badge">Status: idle</span>
                            <span id="drawer-id" class="task-id">ID: ...</span>
                        </div>
                        <div class="stage-badge" id="drawer-stage-badge">Stage 1</div>
                    </div>
                    <div class="drawer-actions">
                        <button class="btn btn-danger btn-sm" onclick="Kanban.deleteTask(Kanban.activeTaskId)">
                            🗑️ Delete Task
                        </button>
                    </div>
                    <div class="drawer-body">
                        <div class="drawer-section">
                            <h3>Current Output</h3>
                            <div id="drawer-artifact" class="artifact-box" style="white-space: pre-wrap; font-family: monospace; font-size: 0.85em; max-height: 300px; overflow-y: auto;">
                                Waiting for output...
                            </div>
                        </div>
                        <div id="notion-section" class="drawer-section hidden">
                            <h3>Published to Notion</h3>
                            <a id="notion-link" href="#" target="_blank" class="notion-link">
                                Open in Notion →
                            </a>
                        </div>
                        <div class="drawer-section">
                            <h3>Agent Monologue</h3>
                            <div id="drawer-thoughts" class="thought-log" data-task-id=""></div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },
    
    async refresh() {
        try {
            const data = await api('/api/kanban/tasks');
            this.tasks = data.tasks || [];
            this._renderBoard();
            
            // Update drawer if open
            if (this.activeTaskId) {
                const activeTask = this.tasks.find(t => t.id === this.activeTaskId);
                if (activeTask) this._updateDrawer(activeTask);
            }
        } catch (err) {
            console.error('Kanban refresh failed:', err);
        }
    },
    
    _renderBoard() {
        for (let stage = 1; stage <= 6; stage++) {
            const list = document.getElementById(`stage-${stage}`);
            const countEl = document.getElementById(`count-${stage}`);
            if (!list) continue;
            
            const stageTasks = this.tasks.filter(t => t.stage == stage);
            list.innerHTML = '';
            stageTasks.forEach(task => {
                list.appendChild(this._createTaskCard(task));
            });
            if (countEl) countEl.textContent = stageTasks.length;
        }
    },
    
    _createTaskCard(task) {
        const card = document.createElement('div');
        card.className = `kanban-task-card ${task.status === 'thinking' ? 'thinking' : ''}`;
        card.dataset.id = task.id;
        card.draggable = true;
        card.style.borderLeftColor = task.color || '#555';
        
        const safeTitle = escHtml(task.title || 'Untitled');
        const safeStatus = escHtml(task.status || 'idle');
        
        card.innerHTML = `
            <div class="task-card-header">
                <span class="task-title">${safeTitle}</span>
            </div>
            <div class="task-card-body">
                <span class="task-status ${STATUS_STYLES[task.status] || ''}">${safeStatus}</span>
                <span class="task-time">${fmtTime(task.updated_at)}</span>
            </div>
        `;
        
        card.onclick = () => this.openDrawer(task.id);
        card.ondragstart = (e) => {
            e.dataTransfer.setData('text/plain', task.id);
            card.classList.add('dragging');
        };
        card.ondragend = () => card.classList.remove('dragging');
        
        return card;
    },
    
    _setupEventListeners() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeDrawer();
        });
    },
    
    _setupDragAndDrop() {
        const columns = document.querySelectorAll('.kanban-column');
        columns.forEach(col => {
            col.ondragover = (e) => {
                e.preventDefault();
                col.classList.add('drag-over');
            };
            col.ondragleave = () => col.classList.remove('drag-over');
            col.ondrop = async (e) => {
                e.preventDefault();
                col.classList.remove('drag-over');
                const taskId = e.dataTransfer.getData('text/plain');
                const newStage = parseInt(col.dataset.stage);
                await this._moveTask(taskId, newStage);
            };
        });
    },
    
    async _moveTask(taskId, stage) {
        try {
            await api(`/api/kanban/tasks/${taskId}`, {
                method: 'PATCH',
                body: { stage }
            });
            // The result will be handled by SSE refresh
        } catch (err) {
            showToast('Cannot move task: ' + err.message, 'error');
        }
    },
    
    async createTask() {
        const title = prompt("Enter a topic or genre for the new content pipeline:");
        if (!title) return;
        
        try {
            const result = await api('/api/kanban/topic-finder', {
                method: 'POST',
                body: { seed_query: title }
            });
            showToast('Pipeline started!', 'success');
            await this.refresh();
        } catch (err) {
            showToast('Failed to start pipeline: ' + err.message, 'error');
        }
    },
    
    async deleteTask(taskId) {
        if (!confirm('Are you sure you want to delete this pipeline run?')) return;
        try {
            await api(`/api/kanban/tasks/${taskId}`, { method: 'DELETE' });
            showToast('Deleted', 'success');
            this.closeDrawer();
            await this.refresh();
        } catch (err) {
            showToast('Delete failed', 'error');
        }
    },
    
    openDrawer(taskId) {
        const task = this.tasks.find(t => t.id === taskId);
        if (!task) return;
        this.activeTaskId = taskId;
        this._updateDrawer(task);
        const drawer = document.getElementById('kanban-drawer');
        drawer.classList.remove('hidden');
        drawer.style.display = '';
    },
    
    _updateDrawer(task) {
        document.getElementById('drawer-title').textContent = task.title || 'Untitled';
        const statusEl = document.getElementById('drawer-status');
        if (statusEl) {
            statusEl.textContent = `Status: ${task.status || 'idle'}`;
            statusEl.className = `task-status-badge ${STATUS_STYLES[task.status] || ''}`;
        }
        document.getElementById('drawer-id').textContent = `ID: ${task.id?.substring(0, 8) || '...'}`;
        
        const stageBadge = document.getElementById('drawer-stage-badge');
        const config = KANBAN_STAGES[task.stage] || KANBAN_STAGES[1];
        stageBadge.textContent = config.name;
        stageBadge.style.background = config.color;
        
        const artifactBox = document.getElementById('drawer-artifact');
        if (artifactBox) {
            let content = 'No output available yet.';
            if (task.stage == 3) content = task.research || 'Research in progress...';
            else if (task.stage == 4) content = task.script || 'Script writing...';
            else if (task.stage == 5) content = task.visual_cues || 'Visual planning...';
            else if (task.stage == 6) content = task.script || 'Complete';
            artifactBox.textContent = content;
        }
        
        const notionSection = document.getElementById('notion-section');
        const notionLink = document.getElementById('notion-link');
        if (task.notion_url) {
            notionSection.classList.remove('hidden');
            notionLink.href = task.notion_url;
        } else {
            notionSection.classList.add('hidden');
        }
    },
    
    closeDrawer() {
        this.activeTaskId = null;
        const drawer = document.getElementById('kanban-drawer');
        if (drawer) {
            drawer.classList.add('hidden');
            drawer.style.display = 'none';
        }
    },
    
    handleSSEEvent(event) {
        const { type } = event;
        switch (type) {
            case 'pipeline_update':
            case 'stage_complete':
            case 'human_gate':
            case 'pipeline_complete':
            case 'task_created':
            case 'task_updated':
            case 'task_deleted':
                this.refresh();
                break;
            case 'agent_event':
                if (event.data.event_type === 'thought' && this.activeTaskId === event.data.task_id) {
                    this._appendThought(event.data.data);
                }
                break;
        }
    },
    
    _appendThought(thought) {
        const thoughtLog = document.getElementById('drawer-thoughts');
        if (!thoughtLog) return;
        const item = document.createElement('div');
        item.className = 'thought-item';
        const time = fmtTime(new Date().toISOString());
        const text = escHtml(thought.content || thought.text || '');
        item.innerHTML = `<span class="thought-time">${time}</span><span class="thought-text">${text}</span>`;
        thoughtLog.appendChild(item);
        thoughtLog.scrollTop = thoughtLog.scrollHeight;
    }
};

window.Kanban = Kanban;
