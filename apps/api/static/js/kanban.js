/**
 * kanban.js — Kanban board management for YouTube Pipeline.
 * 
 * This module implements a 6-column Kanban board for tracking content production:
 *   1. Topic Finding - Topic finder agents discovering trends
 *   2. Suggested Topics - Topics discovered, awaiting approval
 *   3. Researching - Deep research on approved topics
 *   4. Script - Script writing in progress
 *   5. Visual - Visual planning and asset creation
 *   6. Notion - Published to Notion, complete
 * 
 * Features:
 *   - Drag and drop tasks between columns
 *   - Real-time updates via SSE
 *   - Task detail drawer with agent monologue
 *   - Color inheritance for child tasks
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
    
    /**
     * Initialize the Kanban board.
     * Called when the Kanban tab is first activated.
     */
    async init() {
        if (this.initialized) {
            await this.refresh();
            return;
        }
        
        console.log('Kanban: initializing...');
        
        const container = document.getElementById('tab-kanban');
        if (!container) {
            console.error('Kanban: tab-kanban container not found');
            return;
        }
        
        // Render initial HTML structure
        container.innerHTML = this._getBoardHTML();
        
        // Fetch and render tasks
        await this.refresh();
        
        // Setup event handlers
        this._setupEventListeners();
        this._setupDragAndDrop();
        
        this.initialized = true;
        console.log('Kanban: initialized');
    },
    
    /**
     * Generate the Kanban board HTML structure.
     */
    _getBoardHTML() {
        return `
            <div class="kanban-header">
                <h2 class="kanban-title">Content Pipeline</h2>
                <div class="kanban-actions">
                    <button class="btn btn-primary btn-sm" onclick="Kanban.createTask()">
                        + New Topic
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
                            <div class="column-add">
                                ${stage == 1 ? '<button class="add-task-btn" onclick="Kanban.createTask(1)">+ Add</button>' : ''}
                            </div>
                            <div class="task-list" id="stage-${stage}"></div>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <!-- Task Detail Drawer -->
            <div id="kanban-drawer" class="kanban-drawer hidden">
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
                            <div id="drawer-artifact" class="artifact-box">
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
    
    /**
     * Refresh tasks from the API.
     */
    async refresh() {
        try {
            const resp = await fetch('/api/kanban/tasks');
            const data = await resp.json();
            this.tasks = data.tasks || [];
            this._renderBoard();
        } catch (err) {
            console.error('Kanban: failed to fetch tasks', err);
            showToast('Failed to load Kanban tasks', 'error');
        }
    },
    
    /**
     * Render all tasks to the board.
     */
    _renderBoard() {
        // Clear and populate each column
        for (let stage = 1; stage <= 6; stage++) {
            const list = document.getElementById(`stage-${stage}`);
            const countEl = document.getElementById(`count-${stage}`);
            
            if (!list) continue;
            
            const stageTasks = this.tasks.filter(t => t.stage === stage);
            
            list.innerHTML = '';
            stageTasks.forEach(task => {
                list.appendChild(this._createTaskCard(task));
            });
            
            if (countEl) {
                countEl.textContent = stageTasks.length;
            }
        }
    },
    
    /**
     * Create a task card element.
     */
    _createTaskCard(task) {
        const card = document.createElement('div');
        card.className = `kanban-task-card ${task.status === 'thinking' ? 'thinking' : ''}`;
        card.dataset.id = task.id;
        card.draggable = true;
        
        // Set color from task or inherit
        card.style.borderLeftColor = task.color || '#555';
        
        const safeTitle = escHtml(task.title || 'Untitled');
        const safeStatus = escHtml(task.status || 'idle');
        const stageConfig = KANBAN_STAGES[task.stage] || KANBAN_STAGES[1];
        
        card.innerHTML = `
            <div class="task-card-header">
                <span class="task-title">${safeTitle}</span>
            </div>
            <div class="task-card-body">
                <span class="task-status ${STATUS_STYLES[task.status] || ''}">${safeStatus}</span>
                <span class="task-time">${fmtTime(task.updated_at)}</span>
            </div>
        `;
        
        // Click to open drawer
        card.onclick = (e) => {
            if (!e.target.classList.contains('task-delete-btn')) {
                this.openDrawer(task.id);
            }
        };
        
        // Drag handlers
        card.ondragstart = (e) => {
            e.dataTransfer.setData('text/plain', task.id);
            card.classList.add('dragging');
        };
        
        card.ondragend = () => {
            card.classList.remove('dragging');
        };
        
        return card;
    },
    
    /**
     * Setup click event listeners.
     */
    _setupEventListeners() {
        // Close drawer on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeDrawer();
            }
        });
    },
    
    /**
     * Setup drag and drop between columns.
     */
    _setupDragAndDrop() {
        const columns = document.querySelectorAll('.kanban-column');
        
        columns.forEach(col => {
            col.ondragover = (e) => {
                e.preventDefault();
                col.classList.add('drag-over');
            };
            
            col.ondragleave = () => {
                col.classList.remove('drag-over');
            };
            
            col.ondrop = async (e) => {
                e.preventDefault();
                col.classList.remove('drag-over');
                
                const taskId = e.dataTransfer.getData('text/plain');
                const newStage = parseInt(col.dataset.stage);
                
                await this._moveTask(taskId, newStage);
            };
        });
    },
    
    /**
     * Move a task to a different stage.
     */
    async _moveTask(taskId, stage) {
        try {
            await api(`/api/kanban/tasks/${taskId}`, {
                method: 'PATCH',
                body: { stage }
            });
            showToast(`Task moved to ${KANBAN_STAGES[stage]?.name || 'Stage ' + stage}`, 'success');
        } catch (err) {
            showToast('Failed to move task', 'error');
        }
    },
    
    /**
     * Create a new task.
     */
    async createTask(stage = 1) {
        // Show a modal for creating tasks with option to trigger topic finder
        const modal = document.createElement('div');
        modal.className = 'task-create-modal';
        modal.innerHTML = `
            <div class="modal-overlay" onclick="this.parentElement.remove()"></div>
            <div class="modal-content">
                <h3>Create New Task</h3>
                <div class="form-group">
                    <label for="task-title">Topic or Trend:</label>
                    <input type="text" id="task-title" class="form-input" 
                           placeholder="e.g., AI in healthcare, Pakistan economy...">
                </div>
                <div class="form-group">
                    <label for="task-genre">Genre:</label>
                    <select id="task-genre" class="form-input">
                        <option value="default">Default</option>
                        <option value="tech">Technology</option>
                        <option value="politics">Politics</option>
                        <option value="economy">Economy</option>
                        <option value="culture">Culture</option>
                        <option value="current_situation">Current Situation</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="run-finder" checked>
                        Run Topic Finder Agent (AI will analyze and score viability)
                    </label>
                </div>
                <div class="modal-actions">
                    <button class="btn btn-outline" onclick="this.closest('.task-create-modal').remove()">Cancel</button>
                    <button class="btn btn-primary" id="create-btn">Create Task</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Focus the input
        document.getElementById('task-title').focus();
        
        // Handle create button
        document.getElementById('create-btn').onclick = async () => {
            const title = document.getElementById('task-title').value.trim();
            const genre = document.getElementById('task-genre').value;
            const runFinder = document.getElementById('run-finder').checked;
            
            if (!title) {
                showToast('Please enter a topic', 'warning');
                return;
            }
            
            modal.remove();
            
            try {
                if (runFinder) {
                    // Trigger the Topic Finder agent
                    const result = await api('/api/kanban/topic-finder', {
                        method: 'POST',
                        body: { seed_query: title, genre_id: genre }
                    });
                    showToast(`Topic finder started: ${result.id?.substring(0, 8)}`, 'info');
                } else {
                    // Just create a simple task
                    await api('/api/kanban/tasks', {
                        method: 'POST',
                        body: { title, stage }
                    });
                    showToast('Task created', 'success');
                }
            } catch (err) {
                showToast('Failed to create task', 'error');
            }
        };
        
        // Handle enter key
        document.getElementById('task-title').onkeydown = (e) => {
            if (e.key === 'Enter') {
                document.getElementById('create-btn').click();
            }
        };
    },
    
    /**
     * Delete a task.
     */
    async deleteTask(taskId) {
        if (!confirm('Are you sure you want to delete this task?')) {
            return;
        }
        
        try {
            await api(`/api/kanban/tasks/${taskId}`, {
                method: 'DELETE'
            });
            showToast('Task deleted', 'success');
            this.closeDrawer();
        } catch (err) {
            showToast('Failed to delete task', 'error');
        }
    },
    
    /**
     * Open the task detail drawer.
     */
    openDrawer(taskId) {
        const task = this.tasks.find(t => t.id === taskId);
        if (!task) return;
        
        this.activeTaskId = taskId;
        this._updateDrawer(task);
        
        const drawer = document.getElementById('kanban-drawer');
        const content = document.getElementById('drawer-content');
        
        // Set stage class for color theming
        content.className = `drawer-content stage-${task.stage}`;
        
        drawer.classList.remove('hidden');
    },
    
    /**
     * Update drawer content with task data.
     */
    _updateDrawer(task) {
        document.getElementById('drawer-title').textContent = task.title || 'Untitled';
        
        const statusEl = document.getElementById('drawer-status');
        if (statusEl) {
            statusEl.textContent = `Status: ${task.status || 'idle'}`;
            statusEl.className = `task-status-badge ${STATUS_STYLES[task.status] || ''}`;
        }
        
        const idEl = document.getElementById('drawer-id');
        if (idEl) {
            idEl.textContent = `ID: ${task.id?.substring(0, 8) || '...'}`;
        }
        
        // Stage badge
        const stageBadge = document.getElementById('drawer-stage-badge');
        if (stageBadge) {
            const config = KANBAN_STAGES[task.stage] || KANBAN_STAGES[1];
            stageBadge.textContent = config.name;
            stageBadge.style.background = config.color;
        }
        
        // Artifact display
        const artifactBox = document.getElementById('drawer-artifact');
        if (artifactBox) {
            let content = '';
            if (task.stage === 3) content = task.research || 'Researching...';
            else if (task.stage === 4) content = task.script || 'Writing script...';
            else if (task.stage === 5) content = task.visual_cues || 'Planning visuals...';
            else if (task.stage === 6) content = task.script || task.content || 'Complete';
            else content = task.content || 'Waiting for output...';
            artifactBox.textContent = content;
        }
        
        // Notion link
        const notionSection = document.getElementById('notion-section');
        const notionLink = document.getElementById('notion-link');
        if (notionSection && notionLink) {
            if (task.notion_url) {
                notionSection.classList.remove('hidden');
                notionLink.href = task.notion_url;
            } else {
                notionSection.classList.add('hidden');
            }
        }
        
        // Thoughts
        const thoughtLog = document.getElementById('drawer-thoughts');
        if (thoughtLog && thoughtLog.dataset.taskId !== task.id) {
            thoughtLog.innerHTML = '';
            thoughtLog.dataset.taskId = task.id;
            
            try {
                const thoughts = JSON.parse(task.thoughts || '[]');
                thoughts.forEach(t => this._appendThought(t));
            } catch (e) {
                console.error('Failed to parse thoughts:', e);
            }
        }
    },
    
    /**
     * Append a thought to the monologue log.
     */
    _appendThought(thought) {
        const thoughtLog = document.getElementById('drawer-thoughts');
        if (!thoughtLog) return;
        
        const item = document.createElement('div');
        item.className = 'thought-item';
        
        const time = thought.timestamp 
            ? fmtTime(thought.timestamp)
            : new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
        const text = escHtml(thought.content || thought.text || '');
        
        item.innerHTML = `
            <span class="thought-time">${time}</span>
            <span class="thought-text">${text}</span>
        `;
        
        thoughtLog.appendChild(item);
        thoughtLog.scrollTop = thoughtLog.scrollHeight;
    },
    
    /**
     * Close the drawer.
     */
    closeDrawer() {
        this.activeTaskId = null;
        const drawer = document.getElementById('kanban-drawer');
        if (drawer) {
            drawer.classList.add('hidden');
        }
        
        const thoughtLog = document.getElementById('drawer-thoughts');
        if (thoughtLog) {
            thoughtLog.dataset.taskId = '';
        }
    },
    
    /**
     * Handle SSE events for real-time updates.
     * Called from app.js when kanban events are received.
     */
    handleSSEEvent(event) {
        const { type, data } = event;
        
        switch (type) {
            case 'task_created':
                this.tasks.unshift(data);
                this._renderBoard();
                break;
                
            case 'task_updated':
                const idx = this.tasks.findIndex(t => t.id === data.id);
                if (idx !== -1) {
                    this.tasks[idx] = { ...this.tasks[idx], ...data };
                    this._renderBoard();
                    if (this.activeTaskId === data.id) {
                        this._updateDrawer(this.tasks[idx]);
                    }
                }
                break;
                
            case 'task_deleted':
                this.tasks = this.tasks.filter(t => t.id !== data.id);
                this._renderBoard();
                if (this.activeTaskId === data.id) {
                    this.closeDrawer();
                }
                break;
                
            case 'agent_event':
                if (data.event_type === 'thought' && this.activeTaskId === data.task_id) {
                    this._appendThought(data.data);
                }
                // Refresh on stage/status changes
                if (data.event_type === 'stage_change' || data.event_type === 'status_change') {
                    this.refresh();
                }
                break;
        }
    }
};

// Register tab init function
if (typeof TAB_INITS !== 'undefined') {
    TAB_INITS.kanban = () => Kanban.init();
}
if (typeof TAB_REFRESH !== 'undefined') {
    TAB_REFRESH.kanban = () => Kanban.refresh();
}

// Export for global access
window.Kanban = Kanban;
