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

// ─── Toast ────────────────────────────────────────────────────────────────────

function showToast(msg, type = 'info', duration = 4000) {
  const c = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(() => el.remove(), duration);
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
  chat:      () => initChat(),
  providers: () => initProviders(),
  memory:    () => initMemory(),
  analytics: () => initAnalytics(),
  visual:    () => initVisual(),
  settings:  () => initSettings(),
};

const TAB_REFRESH = {
  pipeline:  () => refreshPipeline(),
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

// ─── SSE ─────────────────────────────────────────────────────────────────────

let _es = null;

function connectSSE() {
  if (_es) _es.close();
  _es = new EventSource('/api/events');

  _es.addEventListener('pipeline_update', e => {
    const d = JSON.parse(e.data).data;
    if (_activeTab === 'pipeline') refreshPipeline();
    showToast(`${d.stage} → ${d.status}`, 'info', 2500);
  });

  _es.addEventListener('stage_complete', e => {
    const d = JSON.parse(e.data).data;
    showToast(`✓ ${d.stage} complete`, 'success', 3000);
    if (_activeTab === 'pipeline') refreshPipeline();
  });

  _es.addEventListener('human_gate', e => {
    const d = JSON.parse(e.data).data;
    showToast(`Action needed: ${d.stage}`, 'warning', 6000);
    const badge = document.getElementById('pipeline-badge');
    const n = parseInt(badge.textContent || '0') + 1;
    badge.textContent = n;
    badge.classList.remove('hidden');
    if (_activeTab === 'pipeline') refreshPipeline();
  });

  _es.addEventListener('pipeline_complete', e => {
    const d = JSON.parse(e.data).data;
    showToast(`Pipeline complete!`, 'success', 5000);
    if (_activeTab === 'pipeline') refreshPipeline();
  });

  _es.onerror = () => setTimeout(connectSSE, 5000);
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
  connectSSE();
  checkHealth();
  setInterval(checkHealth, 30000);
});
