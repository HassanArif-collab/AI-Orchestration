/**
 * kanban.js — Kanban board management.
 * 
 * Direct view of pipeline runs stored in Supabase.
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
    _expiryInterval: null,

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
        this._startExpiryCountdown();
        this.initialized = true;
    },
    
    _getBoardHTML() {
        return `
            <div class="kanban-header">
                <h2 class="kanban-title">Kanban Board</h2>
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
                    <div class="drawer-actions" id="drawer-actions">
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
            
            let stageTasks = this.tasks.filter(t => t.stage == stage);

            // Auto-sort stage 2 (Suggested Topics) by expires_at — most urgent first
            if (stage === 2) {
                stageTasks.sort((a, b) => {
                    if (!a.expires_at && !b.expires_at) return 0;
                    if (!a.expires_at) return 1;  // no expiration goes to bottom
                    if (!b.expires_at) return -1;
                    return new Date(a.expires_at) - new Date(b.expires_at);
                });
            }

            list.innerHTML = '';
            stageTasks.forEach(task => {
                list.appendChild(this._createTaskCard(task));
            });
            if (countEl) countEl.textContent = stageTasks.length;
        }
    },
    
    _getExpiryInfo(task) {
        if (!task.expires_at) return null;

        const now = Date.now();
        const expires = new Date(task.expires_at).getTime();
        const remaining = expires - now;

        if (remaining <= 0) {
            return { level: 'expired', label: 'EXPIRED', remaining: 0, cssClass: 'expired' };
        }

        const mins = Math.floor(remaining / 60000);
        const hrs = Math.floor(mins / 60);
        const leftoverMins = mins % 60;

        if (mins < 30) {
            return { level: 'danger', label: `EXPIRING SOON`, remaining, cssClass: 'danger', mins };
        } else if (mins < 60) {
            return { level: 'danger', label: `Expires in ${mins}m`, remaining, cssClass: 'danger', mins };
        } else if (mins < 120) {
            const timeStr = `${leftoverMins}m`;
            return { level: 'warning', label: `⏱ ${timeStr}`, remaining, cssClass: 'warning', mins };
        } else {
            const hStr = String(hrs).padStart(2, '0');
            const mStr = String(leftoverMins).padStart(2, '0');
            return { level: 'normal', label: `Due: ${hStr}:${mStr}`, remaining, cssClass: 'normal', mins };
        }
    },

    _createTaskCard(task) {
        const card = document.createElement('div');
        const expiryInfo = this._getExpiryInfo(task);
        const urgencyClass = expiryInfo ? `urgency-${expiryInfo.level}` : '';
        const isThinking = task.status === 'thinking';
        card.className = `kanban-task-card ${isThinking ? 'thinking' : ''} ${urgencyClass}`.trim();
        card.dataset.id = task.id;
        card.draggable = true;

        // Set border-left color based on urgency or task color
        if (expiryInfo) {
            // urgency CSS classes handle border-left-color
        } else {
            card.style.borderLeftColor = task.color || '#555';
        }

        // Set data-expires-at attribute for countdown updates
        if (task.expires_at) {
            card.dataset.expiresAt = task.expires_at;
        }
        
        const safeTitle = escHtml(task.title || 'Untitled');
        const safeStatus = escHtml(task.status || 'idle');
        
        let expiryHtml = '';
        if (expiryInfo) {
            expiryHtml = `<div class="expiry-badge ${expiryInfo.cssClass}" data-expiry-badge="${task.id}">${expiryInfo.label}</div>`;
        }

        let extendHtml = '';
        if (expiryInfo && (expiryInfo.level === 'danger' || expiryInfo.level === 'expired')) {
            extendHtml = `<button class="extend-btn" onclick="event.stopPropagation();Kanban.extendCardExpiry('${task.id}')">Extend 3h</button>`;
        }

        // Thinking progress indicator with estimated time
        let thinkingHtml = '';
        if (isThinking) {
            const elapsed = task.thinking_started_at ? Math.floor((Date.now() - new Date(task.thinking_started_at).getTime()) / 1000) : null;
            let timeText = '';
            if (elapsed && elapsed > 10) {
                const mins = Math.floor(elapsed / 60);
                const secs = elapsed % 60;
                timeText = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
            }
            thinkingHtml = `<div class="thinking-progress">${timeText ? `⏳ ${timeText}` : '⏳ Processing...'}</div>`;
        }
        
        card.innerHTML = `
            <div class="task-card-header">
                <span class="task-title">${safeTitle}</span>
            </div>
            <div class="task-card-body">
                <span class="task-status ${STATUS_STYLES[task.status] || ''}">${safeStatus}</span>
                ${expiryHtml}
                <span class="task-time">${fmtTime(task.updated_at)}</span>
            </div>
            ${thinkingHtml}
            ${extendHtml}
        `;
        
        card.onclick = () => this.openDrawer(task.id);
        card.ondragstart = (e) => {
            e.dataTransfer.setData('text/plain', task.id);
            card.classList.add('dragging');
        };
        card.ondragend = () => card.classList.remove('dragging');
        
        return card;
    },

    async extendCardExpiry(taskId) {
        try {
            await api(`/api/kanban/tasks/${taskId}`, {
                method: 'PATCH',
                body: { extend_expiration: true }
            });
            showToast('Expiration extended by 3 hours', 'success');
            await this.refresh();
        } catch (err) {
            showToast('Failed to extend: ' + err.message, 'error');
        }
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
        const title = prompt("Enter a topic or genre for the new task:");
        if (!title) return;
        
        try {
            const result = await api('/api/kanban/topic-finder', {
                method: 'POST',
                body: { seed_query: title }
            });
            showToast('Task started!', 'success');
            await this.refresh();
        } catch (err) {
            showToast('Failed to start task: ' + err.message, 'error');
        }
    },
    
    async deleteTask(taskId) {
        try {
            await api(`/api/kanban/tasks/${taskId}/soft-delete`, { method: 'POST' });
            this.closeDrawer();
            showUndoToast('Task deleted', async () => {
                try {
                    await api(`/api/kanban/tasks/${taskId}/undo-delete`, { method: 'POST' });
                    showToast('Run restored', 'success');
                    await this.refresh();
                } catch (err) {
                    showToast('Restore failed: ' + err.message, 'error');
                }
            });
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
        
        // Show contextual action buttons based on task status
        const actionsEl = document.getElementById('drawer-actions');
        const isWaiting = task.status === 'waiting';
        const isError = task.status === 'error';
        const nextStage = task.stage < 6 ? task.stage + 1 : null;
        
        actionsEl.innerHTML = '';

        // Show error message if task has one
        if (task.error_message) {
            const errorBanner = document.createElement('div');
            errorBanner.className = 'error-banner';
            errorBanner.style.cssText = 'background:#3d1a1a;border:1px solid #d1242f;border-radius:6px;padding:8px 12px;margin-bottom:8px;font-size:12px;color:#ff6b6b;max-width:100%;word-wrap:break-word;';
            errorBanner.textContent = '⚠️ ' + task.error_message;
            actionsEl.appendChild(errorBanner);
        }
        
        // Approve / Resume button for waiting or error tasks
        if ((isWaiting || isError) && nextStage) {
            const approveBtn = document.createElement('button');
            approveBtn.className = 'btn btn-primary btn-sm';
            approveBtn.style.marginRight = '8px';
            approveBtn.textContent = isWaiting 
                ? `✅ Approve & Start ${KANBAN_STAGES[nextStage]?.name || 'Next Stage'}` 
                : `🔄 Retry & Continue`;
            approveBtn.onclick = async () => {
                approveBtn.disabled = true;
                approveBtn.textContent = '⏳ Starting...';
                try {
                    await api(`/api/kanban/tasks/${task.id}`, {
                        method: 'PATCH',
                        body: { stage: nextStage }
                    });
                    showToast('Pipeline resumed!', 'success');
                    this.closeDrawer();
                    await this.refresh();
                } catch (err) {
                    showToast('Failed: ' + err.message, 'error');
                    approveBtn.disabled = false;
                    approveBtn.textContent = isWaiting 
                        ? `✅ Approve & Start ${KANBAN_STAGES[nextStage]?.name || 'Next Stage'}` 
                        : `🔄 Retry & Continue`;
                }
            };
            actionsEl.appendChild(approveBtn);
        }
        
        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn-danger btn-sm';
        deleteBtn.textContent = '🗑️ Delete Task';
        deleteBtn.onclick = () => this.deleteTask(this.activeTaskId);
        actionsEl.appendChild(deleteBtn);
        
        const artifactBox = document.getElementById('drawer-artifact');
        if (artifactBox) {
            let content = 'No output available yet.';
            if (task.stage == 3) content = task.research || 'Research in progress...';
            else if (task.stage == 4) content = task.script || 'Script writing...';
            else if (task.stage == 5) content = task.visual_cues || 'Visual planning...';
            else if (task.stage == 6) content = task.script || 'Complete';
            // Use innerHTML to render HTML content (Task 6 fix)
            artifactBox.innerHTML = content;
        }
        
        const notionSection = document.getElementById('notion-section');
        const notionLink = document.getElementById('notion-link');
        if (task.notion_url) {
            notionSection.classList.remove('hidden');
            notionLink.href = task.notion_url;
        } else {
            notionSection.classList.add('hidden');
        }
        
        // Render thoughts if available
        const thoughtsEl = document.getElementById('drawer-thoughts');
        if (thoughtsEl) {
            if (task.thoughts) {
                try {
                    const thoughtsList = typeof task.thoughts === 'string' ? JSON.parse(task.thoughts) : task.thoughts;
                    if (Array.isArray(thoughtsList) && thoughtsList.length > 0) {
                        thoughtsEl.innerHTML = thoughtsList.map(t => {
                            const time = fmtTime(t.time || t.created_at || new Date().toISOString());
                            const text = escHtml(t.content || t.text || '');
                            const typeIcon = t.thought_type === 'error' ? '🔴' :
                                             t.thought_type === 'output' ? '✅' :
                                             t.thought_type === 'search' ? '🔍' : '💭';
                            return `<div class="thought-item"><span class="thought-time">${time}</span><span class="thought-text">${typeIcon} [${escHtml(t.agent_name || 'agent')}] ${text}</span></div>`;
                        }).join('');
                    } else {
                        thoughtsEl.innerHTML = '<div style="color:var(--text-muted);font-size:12px;">No agent thoughts recorded yet — thoughts will appear as the pipeline runs.</div>';
                    }
                } catch (e) {
                    thoughtsEl.innerHTML = '<div style="color:var(--text-muted);font-size:12px;">No agent thoughts recorded yet.</div>';
                }
            } else {
                thoughtsEl.innerHTML = '<div style="color:var(--text-muted);font-size:12px;">No agent thoughts recorded yet — thoughts will appear as the pipeline runs.</div>';
            }
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
    },

    // ─── Expiration Countdown Timer ───────────────────────────────────────────

    _startExpiryCountdown() {
        // Update every 30 seconds
        this._expiryInterval = setInterval(() => {
            // Only run if kanban tab is active
            if (typeof _activeTab !== 'undefined' && _activeTab !== 'kanban') return;
            this._updateExpiryBadges();
        }, 30000);
    },

    _updateExpiryBadges() {
        // Find all cards with expiration data and update their badges
        const cards = document.querySelectorAll('.kanban-task-card[data-expires-at]');
        cards.forEach(card => {
            const expiresAt = card.dataset.expiresAt;
            if (!expiresAt) return;

            const taskId = card.dataset.id;
            const task = this.tasks.find(t => t.id === taskId);
            if (!task) return;

            const expiryInfo = this._getExpiryInfo(task);
            if (!expiryInfo) return;

            // Update badge text
            const badge = card.querySelector(`[data-expiry-badge="${taskId}"]`);
            if (badge) {
                badge.textContent = expiryInfo.label;
                badge.className = `expiry-badge ${expiryInfo.cssClass}`;
            }

            // Update urgency class on card
            card.classList.remove('urgency-normal', 'urgency-warning', 'urgency-danger', 'urgency-expired');
            card.classList.add(`urgency-${expiryInfo.level}`);

            // Show/hide extend button
            const existingExtend = card.querySelector('.extend-btn');
            if (expiryInfo.level === 'danger' || expiryInfo.level === 'expired') {
                if (!existingExtend) {
                    const btn = document.createElement('button');
                    btn.className = 'extend-btn';
                    btn.textContent = 'Extend 3h';
                    btn.onclick = (e) => {
                        e.stopPropagation();
                        this.extendCardExpiry(taskId);
                    };
                    card.appendChild(btn);
                }
            } else if (existingExtend) {
                existingExtend.remove();
            }
        });
    }
};

window.Kanban = Kanban;
