/* pipeline.js — FreeRouter Kanban Pipeline Logic */

const Pipeline = {
  tasks: [],
  activeTaskId: null,
  eventSource: null,

  async init() {
    console.log("Pipeline: initializing...");
    await this.fetchTasks();
    this.renderBoard();
    this.setupEventListeners();
    this.setupSSE();
    this.setupDragAndDrop();
  },

  async fetchTasks() {
    try {
      const resp = await fetch('/api/pipeline/tasks');
      const data = await resp.json();
      this.tasks = data.tasks || [];
    } catch (err) {
      console.error("Pipeline: failed to fetch tasks", err);
      UI.toast("Failed to load pipeline tasks", "error");
    }
  },

  renderBoard() {
    const columns = document.querySelectorAll('.kanban-column');
    columns.forEach(col => {
      const stage = parseInt(col.dataset.stage);
      const list = col.querySelector('.task-list');
      list.innerHTML = '';

      const stageTasks = this.tasks.filter(t => t.stage === stage);
      stageTasks.forEach(task => {
        const card = this.createTaskCard(task);
        list.appendChild(card);
      });
    });
  },

  createTaskCard(task) {
    const card = document.createElement('div');
    card.className = `task-card ${task.status === 'thinking' ? 'active' : ''}`;
    card.dataset.id = task.id;
    card.draggable = true;
    card.style.borderLeftColor = task.color || '#ccc';

    card.innerHTML = `
      <div class="task-title">${UI.escapeHtml(task.title)}</div>
      <div class="task-meta">
        <span class="task-status">${task.status}</span>
        <span class="task-time">${this.formatTime(task.updated_at)}</span>
      </div>
    `;

    card.onclick = () => this.openDrawer(task.id);
    
    card.ondragstart = (e) => {
      e.dataTransfer.setData('text/plain', task.id);
      card.classList.add('dragging');
    };

    card.ondragend = () => {
      card.classList.remove('dragging');
    };

    return card;
  },

  formatTime(iso) {
    if (!iso) return '';
    const date = new Date(iso);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  },

  setupEventListeners() {
    // Add task buttons
    document.querySelectorAll('.add-task-btn').forEach(btn => {
      btn.onclick = async () => {
        const title = prompt("Enter topic or trend to analyze:");
        if (title) {
          await this.createTask(title, parseInt(btn.dataset.stage));
        }
      };
    });

    // Drawer close
    document.querySelector('.close-drawer').onclick = () => this.closeDrawer();
    document.querySelector('.drawer-overlay').onclick = () => this.closeDrawer();
  },

  async createTask(title, stage) {
    try {
      const resp = await fetch('/api/pipeline/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, stage })
      });
      if (resp.ok) {
        UI.toast("Task created", "success");
        // Task will be added via SSE
      }
    } catch (err) {
      UI.toast("Failed to create task", "error");
    }
  },

  setupSSE() {
    if (this.eventSource) this.eventSource.close();

    this.eventSource = new EventSource('/api/pipeline/stream');
    
    this.eventSource.onmessage = (e) => {
      const event = JSON.parse(e.data);
      console.log("Pipeline: SSE event", event);

      if (event.type === 'task_created') {
        this.tasks.unshift(event.task);
        this.renderBoard();
      } else if (event.type === 'task_updated') {
        const idx = this.tasks.findIndex(t => t.id === event.task.id);
        if (idx !== -1) {
          this.tasks[idx] = event.task;
          this.renderBoard();
          if (this.activeTaskId === event.task.id) {
            this.updateDrawer(event.task);
          }
        }
      } else if (event.type === 'task_deleted') {
        this.tasks = this.tasks.filter(t => t.id !== event.task_id);
        this.renderBoard();
        if (this.activeTaskId === event.task_id) this.closeDrawer();
      } else if (event.type === 'agent_event') {
        this.handleAgentEvent(event);
      }
    };

    this.eventSource.onerror = () => {
      console.error("Pipeline: SSE connection lost. Reconnecting...");
    };
  },

  handleAgentEvent(event) {
    const { task_id, event_type, data } = event;
    const task = this.tasks.find(t => t.id === task_id);
    if (!task) return;

    if (event_type === 'thought' && this.activeTaskId === task_id) {
      this.appendThought(data);
    }
    
    // Most events will trigger a 'task_updated' from server anyway, 
    // but we can optimize local UI here if needed.
  },

  setupDragAndDrop() {
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
        
        await this.moveTask(taskId, newStage);
      };
    });
  },

  async moveTask(taskId, stage) {
    try {
      const resp = await fetch(`/api/pipeline/tasks/${taskId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage })
      });
      if (!resp.ok) UI.toast("Failed to move task", "error");
    } catch (err) {
      UI.toast("Network error", "error");
    }
  },

  openDrawer(taskId) {
    const task = this.tasks.find(t => t.id === taskId);
    if (!task) return;

    this.activeTaskId = taskId;
    this.updateDrawer(task);
    
    const drawer = document.getElementById('task-drawer');
    const content = drawer.querySelector('.drawer-content');
    
    // Reset stage classes
    content.className = 'drawer-content';
    content.classList.add(`stage-${task.stage}`);
    
    drawer.classList.remove('hidden');
  },

  updateDrawer(task) {
    document.getElementById('drawer-title').textContent = task.title;
    document.getElementById('drawer-status').textContent = `Status: ${task.status}`;
    document.getElementById('drawer-id').textContent = `ID: ${task.id.substring(0,8)}`;
    
    const stageBadge = document.getElementById('drawer-stage-badge');
    const stages = ["", "Topic Finding", "Suggested Topics", "Researching", "Scripting", "Visuals", "Notion"];
    stageBadge.textContent = stages[task.stage] || "Stage " + task.stage;

    // Artifacts
    const artifactBox = document.getElementById('drawer-artifact');
    let content = "";
    if (task.stage === 3) content = task.research || "Researching...";
    else if (task.stage === 4) content = task.script || "Writing script...";
    else if (task.stage === 5) content = task.visual_cues || "Generating visual cues...";
    else if (task.stage === 6) content = task.script || task.content || "Final content";
    else content = task.content || "Waiting for output...";
    
    artifactBox.textContent = content;

    // Notion Link
    const notionContainer = document.getElementById('notion-link-container');
    const notionLink = document.getElementById('notion-link');
    if (task.notion_url) {
      notionContainer.classList.remove('hidden');
      notionLink.href = task.notion_url;
    } else {
      notionContainer.classList.add('hidden');
    }

    // Thoughts (if not already rendered)
    const thoughtLog = document.getElementById('drawer-thoughts');
    if (thoughtLog.dataset.taskId !== task.id) {
        thoughtLog.innerHTML = '';
        thoughtLog.dataset.taskId = task.id;
        const thoughts = JSON.parse(task.thoughts || '[]');
        thoughts.forEach(t => this.appendThought(t));
    }
  },

  appendThought(thought) {
    const thoughtLog = document.getElementById('drawer-thoughts');
    const item = document.createElement('div');
    item.className = 'thought-item';
    
    const time = thought.timestamp ? new Date(thought.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
    
    item.innerHTML = `
      <div class="thought-time">${time}</div>
      <div class="thought-text">${UI.escapeHtml(thought.content || thought.text || '')}</div>
    `;
    
    thoughtLog.appendChild(item);
    thoughtLog.scrollTop = thoughtLog.scrollHeight;
  },

  closeDrawer() {
    this.activeTaskId = null;
    document.getElementById('task-drawer').classList.add('hidden');
    document.getElementById('drawer-thoughts').dataset.taskId = '';
  }
};
