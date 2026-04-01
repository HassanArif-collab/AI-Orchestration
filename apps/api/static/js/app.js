/**
 * app.js — Navigation, SSE connection, shared utilities.
 * Must be loaded first. Defines api(), showToast(), showModal(), etc.
 */

// ─── API helper ───────────────────────────────────────────────────────────────

async function api(path, options = {}) {
  const opts = { headers: { 'Content-Type': 'application/json' }, ...options };
  if (opts.body && typeof opts.body === 'object') opts.body = JSON.stringify(opts.body);
  const resp = await fetch(path, opts);
  if (!resp.ok) {
    const text = await resp.text().catch(() => `HTTP ${resp.status}`);
    throw new Error(text || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ─── Toast (enhanced with stacking & action buttons) ─────────────────────────

const MAX_TOASTS = 3;

function showToast(msg, type = 'info', duration = 4000) {
  const c = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(() => el.remove(), duration);
  // Enforce max toast stack
  while (c.children.length > MAX_TOASTS) {
    c.removeChild(c.firstChild);
  }
}

function showToastWithAction(msg, type, actionText, actionFn, duration = 7000) {
  const c = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;

  const msgSpan = document.createElement('span');
  msgSpan.textContent = msg;
  el.appendChild(msgSpan);

  const btn = document.createElement('span');
  btn.className = 'toast-action';
  btn.textContent = actionText;
  btn.onclick = () => { actionFn(); el.remove(); };
  el.appendChild(btn);

  c.appendChild(el);
  setTimeout(() => el.remove(), duration);
  // Enforce max toast stack
  while (c.children.length > MAX_TOASTS) {
    c.removeChild(c.firstChild);
  }
  return el;
}

function showUndoToast(msg, undoFn) {
  return showToastWithAction(msg, 'info', 'Undo', undoFn, 7000);
}

// ─── Modal ────────────────────────────────────────────────────────────────────

function showModal(html) {
  document.getElementById('modal-content').innerHTML = html;
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function hideModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

// ─── Formatting ───────────────────────────────────────────────────────────────

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
}

function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return isNaN(d) ? '' : d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
}

function statusDot(status) {
  return `<span class="status-dot ${status}"></span>`;
}

// ─── Navigation ───────────────────────────────────────────────────────────────

const TAB_INITS = {
  pipeline:  () => initPipeline(),
  kanban:    () => Kanban.init(),
  chat:      () => initChat(),
  providers: () => initProviders(),
  memory:    () => initMemory(),
  analytics: () => initAnalytics(),
  visual:    () => initVisual(),
  settings:  () => initSettings(),
};

const TAB_REFRESH = {
  pipeline:  () => refreshPipeline(),
  kanban:    () => Kanban.refresh(),
  chat:      () => {},
  providers: () => refreshProviders(),
  memory:    () => refreshMemory(),
  analytics: () => refreshAnalytics(),
  visual:    () => refreshVisual(),
  settings:  () => refreshSettings(),
};

let _activeTab = 'pipeline';
const _initialized = {};

function switchTab(name) {
  if (!TAB_INITS[name]) return;
  document.querySelectorAll('.nav-link').forEach(l =>
    l.classList.toggle('active', l.dataset.tab === name));
  document.querySelectorAll('.tab-content').forEach(el =>
    el.classList.toggle('active', el.id === `tab-${name}`));
  _activeTab = name;
  if (!_initialized[name]) {
    _initialized[name] = true;
    TAB_INITS[name]();
  } else {
    TAB_REFRESH[name]();
  }
}

window.addEventListener('hashchange', () => {
  const h = location.hash.replace('#','') || 'pipeline';
  switchTab(h);
});

// ─── SSE (with connection state tracking & progress events) ───────────────────

let _es = null;
let _sseState = 'disconnected'; // 'connected' | 'reconnecting' | 'disconnected'

function setSSEState(state) {
  _sseState = state;
  const el = document.getElementById('sse-status');
  if (!el) return;
  el.className = `sse-status ${state}`;
  const label = state === 'connected' ? 'Live' : state === 'reconnecting' ? 'Reconnecting…' : 'Offline';
  el.innerHTML = `<span class="sse-dot"></span>${label}`;
}

function connectSSE() {
  if (_es) _es.close();
  _es = new EventSource('/api/events');

  setSSEState('connected');

  _es.addEventListener('pipeline_update', e => {
    const d = JSON.parse(e.data).data;
    if (_activeTab === 'pipeline') refreshPipeline();
    if (typeof Kanban !== 'undefined') Kanban.handleSSEEvent({ type: 'pipeline_update', data: d });
    showToast(`${d.stage} → ${d.status}`, 'info', 2500);
  });

  _es.addEventListener('stage_complete', e => {
    const d = JSON.parse(e.data).data;
    showToast(`✓ ${d.stage} complete`, 'success', 3000);
    if (_activeTab === 'pipeline') refreshPipeline();
    if (typeof Kanban !== 'undefined') Kanban.handleSSEEvent({ type: 'stage_complete', data: d });
  });

  _es.addEventListener('human_gate', e => {
    const d = JSON.parse(e.data).data;
    showToast(`Action needed: ${d.stage}`, 'warning', 6000);
    const badge = document.getElementById('pipeline-badge');
    const n = parseInt(badge.textContent || '0') + 1;
    badge.textContent = n;
    badge.classList.remove('hidden');
    if (_activeTab === 'pipeline') refreshPipeline();
    if (typeof Kanban !== 'undefined') Kanban.handleSSEEvent({ type: 'human_gate', data: d });
  });

  _es.addEventListener('pipeline_complete', e => {
    const d = JSON.parse(e.data).data;
    showToast(`Pipeline complete!`, 'success', 5000);
    if (_activeTab === 'pipeline') refreshPipeline();
    if (typeof Kanban !== 'undefined') Kanban.handleSSEEvent({ type: 'pipeline_complete', data: d });
  });

  // Iteration complete events for script improvement
  _es.addEventListener('iteration_complete', e => {
    const d = JSON.parse(e.data).data;
    if (_activeTab === 'pipeline') refreshPipeline();
    showToast(`Iter ${d.iteration}: ${d.score}% ${d.beat_baseline?'↑':'·'} (${(d.mutation_zone||'').replace(/_/g,' ')})`, d.beat_baseline?'success':'info', 2000);
  });

  // Progress events — update progress bars in the UI
  _es.addEventListener('progress', e => {
    try {
      const d = JSON.parse(e.data).data;
      const runId = d.run_id || d.operation_id;
      if (!runId) return;
      const bar = document.getElementById(`progress-bar-${runId}`);
      const label = document.getElementById(`progress-label-${runId}`);
      if (bar && d.progress_percent != null) {
        bar.style.width = `${Math.min(100, d.progress_percent)}%`;
      }
      if (label && d.stage) {
        label.textContent = d.stage;
      }
    } catch (err) {
      // Silently ignore progress parse errors
    }
  });

  // Kanban events
  _es.addEventListener('task_created', e => {
    const d = JSON.parse(e.data);
    if (typeof Kanban !== 'undefined') {
      Kanban.handleSSEEvent({ type: 'task_created', data: d.data });
    }
  });

  _es.addEventListener('task_updated', e => {
    const d = JSON.parse(e.data);
    if (typeof Kanban !== 'undefined') {
      Kanban.handleSSEEvent({ type: 'task_updated', data: d.data });
    }
  });

  _es.addEventListener('task_deleted', e => {
    const d = JSON.parse(e.data);
    if (typeof Kanban !== 'undefined') {
      Kanban.handleSSEEvent({ type: 'task_deleted', data: d.data });
    }
  });

  _es.addEventListener('agent_event', e => {
    const d = JSON.parse(e.data);
    if (typeof Kanban !== 'undefined') {
      Kanban.handleSSEEvent({ type: 'agent_event', data: d.data });
    }
  });

  _es.onerror = () => {
    setSSEState('reconnecting');
    setTimeout(connectSSE, 5000);
  };
}

// ─── Service Health Header Bar ────────────────────────────────────────────────

const SERVICE_DISPLAY_NAMES = {
  zep: 'Zep',
  notion: 'Notion',
  freerouter: 'FreeRouter',
  supabase: 'Supabase',
  exa: 'Exa',
  youtube: 'YouTube'
};

async function loadServiceHealth() {
  const bar = document.getElementById('health-bar');
  if (!bar) return;

  try {
    const data = await api('/api/health/services');
    const services = data.services || data;
    renderHealthBar(services);
  } catch (err) {
    // If the endpoint is not available, show nothing (graceful degradation)
    bar.innerHTML = '';
  }
}

function renderHealthBar(services) {
  const bar = document.getElementById('health-bar');
  if (!bar) return;

  const serviceEntries = Array.isArray(services) ? services : Object.values(services);

  let html = '<div class="health-bar">';

  for (const svc of serviceEntries) {
    const name = SERVICE_DISPLAY_NAMES[svc.name] || svc.name;
    const configStatus = svc.config_status || 'not_configured';
    const operationalStatus = svc.operational_status || 'unknown';
    const message = svc.message || '';

    // Determine overall indicator state
    let indicatorClass, shapeClass, labelText;

    if (operationalStatus === 'available' || operationalStatus === 'healthy' || operationalStatus === 'ok') {
      indicatorClass = 'available';
      shapeClass = 'circle';
      labelText = 'OK';
    } else if (operationalStatus === 'misconfigured' || operationalStatus === 'degraded') {
      indicatorClass = 'misconfigured';
      shapeClass = 'triangle';
      labelText = 'Degraded';
    } else if (configStatus === 'not_configured' || operationalStatus === 'not_configured') {
      indicatorClass = 'not_configured';
      shapeClass = 'square';
      labelText = 'Off';
    } else if (operationalStatus === 'error' || operationalStatus === 'unavailable' || operationalStatus === 'down') {
      indicatorClass = 'error';
      shapeClass = 'diamond';
      labelText = 'Down';
    } else {
      indicatorClass = 'not_configured';
      shapeClass = 'square';
      labelText = 'Off';
    }

    html += `<div class="health-indicator ${indicatorClass}" title="${escHtml(name)}: ${escHtml(message || labelText)}">
      <span class="health-shape ${shapeClass}"></span>
      <span class="health-label">${escHtml(name)}</span>
    </div>`;
  }

  // SSE connection status indicator
  html += `<div id="sse-status" class="sse-status disconnected"><span class="sse-dot"></span>Offline</div>`;

  html += '</div>';
  bar.innerHTML = html;

  // Re-apply current SSE state to the new element
  setSSEState(_sseState);
}

// ─── FreeRouter Health Check ─────────────────────────────────────────────────

async function checkFreeRouter() {
  const banner = document.getElementById('freerouter-banner');
  if (!banner) return;
  
  try {
    const r = await fetch('/api/health/freerouter');
    const d = await r.json();
    if (!d.healthy) {
      // Show banner when health check returns unhealthy
      banner.classList.remove('hidden');
      banner.textContent = '⚠ FreeRouter LLM proxy not running — pipeline runs will fail. Run: cd freerouter && python -m freerouter proxy';
    } else {
      banner.classList.add('hidden');
    }
  } catch(e) {
    // Show banner on network errors, server errors, or JSON parse failures
    // This ensures the banner appears when the health endpoint is unreachable
    banner.classList.remove('hidden');
    banner.textContent = '⚠ FreeRouter health check failed — pipeline runs may fail. Error: ' + e.message;
  }
}

// ─── Health ───────────────────────────────────────────────────────────────────

async function checkHealth() {
  try {
    const h = await api('/api/providers/health');
    const dot = document.getElementById('system-status');
    const cls = h.overall === 'healthy' ? 'online'
              : h.overall === 'degraded' ? 'warning' : 'offline';
    dot.className = `status-dot ${cls}`;
    dot.title = h.overall;
  } catch {
    const dot = document.getElementById('system-status');
    dot.className = 'status-dot offline';
    dot.title = 'offline';
  }
}

// ─── DLQ Badge & Slide-out Panel ─────────────────────────────────────────────

async function checkDLQStatus() {
  const badge = document.getElementById('dlq-badge');
  if (!badge) return;

  try {
    const data = await api('/api/dlq/stats');
    const pending = data.pending || data.stats?.pending || 0;
    if (pending > 0) {
      badge.textContent = pending;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  } catch {
    // DLQ endpoint may not be available; hide badge gracefully
    badge.classList.add('hidden');
  }
}

function showDLQPanel() {
  const panel = document.getElementById('dlq-panel');
  if (!panel) return;
  panel.classList.add('open');
  _loadDLQItems();
}

function closeDLQPanel() {
  const panel = document.getElementById('dlq-panel');
  if (!panel) return;
  panel.classList.remove('open');
}

async function _loadDLQItems() {
  const body = document.getElementById('dlq-panel-body');
  if (!body) return;

  try {
    const data = await api('/api/dlq/items?status=pending');
    const items = data.items || data || [];

    if (!Array.isArray(items) || items.length === 0) {
      body.innerHTML = '<div style="color:var(--text-muted);font-size:12px;text-align:center;padding:40px 20px">✓ No pending failed operations</div>';
      return;
    }

    body.innerHTML = items.map(item => `
      <div class="dlq-item">
        <div class="dlq-item-header">
          <span class="dlq-item-operation">${escHtml(item.operation || item.operation_type || 'Unknown')}</span>
          <span class="dlq-item-meta">${item.attempt ? `Attempt ${item.attempt}` : ''}</span>
        </div>
        ${item.error ? `<div class="dlq-item-error">${escHtml(item.error)}</div>` : ''}
        <div class="dlq-item-meta">
          ${item.created_at ? `Queued: ${fmtDate(item.created_at)}` : ''}
          ${item.error_code ? ` · Code: ${escHtml(item.error_code)}` : ''}
        </div>
        <div class="dlq-item-actions">
          <button class="btn btn-primary btn-sm" onclick="retryDLQItem('${item.id || item.entry_id}')">↻ Retry</button>
          <button class="btn btn-danger btn-sm" onclick="deleteDLQItem('${item.id || item.entry_id}')">🗑 Delete</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    body.innerHTML = `<div style="color:var(--accent-error);font-size:12px;text-align:center;padding:40px 20px">Failed to load DLQ items: ${escHtml(err.message)}</div>`;
  }
}

async function retryDLQItem(itemId) {
  try {
    await api(`/api/dlq/items/${itemId}/retry`, { method: 'POST' });
    showToast('Item marked for retry', 'success');
    _loadDLQItems();
    checkDLQStatus();
  } catch (err) {
    showToast('Retry failed: ' + err.message, 'error');
  }
}

async function deleteDLQItem(itemId) {
  try {
    await api(`/api/dlq/items/${itemId}`, { method: 'DELETE' });
    showToast('Item deleted', 'info');
    _loadDLQItems();
    checkDLQStatus();
  } catch (err) {
    showToast('Delete failed: ' + err.message, 'error');
  }
}

// ─── Bootstrap ───────────────────────────────────────────────────────────────

document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-overlay')) hideModal();
});

document.querySelectorAll('.nav-link').forEach(l => {
  l.addEventListener('click', e => {
    e.preventDefault();
    const tab = l.dataset.tab;
    history.pushState(null, '', `#${tab}`);
    switchTab(tab);
  });
});

// Bootstrap after ALL scripts load so initPipeline/initChat etc. are defined.
// Do NOT call switchTab here — pipeline.js hasn't executed yet at this point.
window.addEventListener('load', () => {
  const _initTab = location.hash.replace('#','') || 'pipeline';
  switchTab(_initTab);
  
  // Bug C Fix: Delay SSE slightly to ensure all modules are registered
  setTimeout(() => {
    connectSSE();
    checkHealth();
    checkFreeRouter();
    loadServiceHealth();
    checkDLQStatus();
  }, 100);
  
  setInterval(checkHealth, 30000);
  setInterval(checkFreeRouter, 30000);
  setInterval(loadServiceHealth, 30000);
  setInterval(checkDLQStatus, 30000);
});
