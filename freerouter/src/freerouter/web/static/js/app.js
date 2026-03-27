/**
 * app.js — Main application logic and tab management.
 */

const App = {
  async init() {
    console.log("FreeRouter App: initializing...");
    this.setupTabs();
    
    // Initial data load for the default active tab (Providers)
    Providers.init();
  },

  setupTabs() {
    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
      tab.onclick = async () => {
        const tabName = tab.dataset.tab;
        
        // UI updates
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
        document.getElementById(`tab-${tabName}`).classList.remove('hidden');
        
        // Lazy load tab data
        if (tabName === 'chat') {
          Chat.init();
        } else if (tabName === 'usage') {
          loadUsage();
        } else if (tabName === 'pipeline') {
          if (typeof Pipeline !== 'undefined') {
            Pipeline.init();
          } else {
            console.error("Pipeline script not loaded");
          }
        } else if (tabName === 'providers') {
          Providers.init();
        }
      };
    });
  }
};

// Start the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => App.init());

// ─── Usage Tab ───────────────────────────────────────────────────────────────

async function loadUsage() {
  const panel = document.getElementById('tab-usage');
  panel.innerHTML = '<div class="loading">Loading usage…</div>';

  try {
    const data = await apiFetch('/usage');
    const usage = data.usage || {};
    const entries = Object.entries(usage);

    const hasAnyData = entries.some(([, u]) => u.has_data);

    panel.innerHTML = `
      <div class="section-header">
        <h2>Rate Limit Usage</h2>
        <p class="muted">
          Where this data comes from: every time you send a message, the provider
          returns rate limit headers in its response (e.g. <code>x-ratelimit-remaining-requests</code>).
          FreeRouter reads those headers and tracks usage here in real time.
          When a provider hits 90%+ usage, FreeRouter automatically switches to the next one.
        </p>
      </div>

      ${!hasAnyData ? `
        <div class="info-box">
          No usage data yet — data appears after your first message in the Chat tab.
          Providers below are configured and ready.
        </div>
      ` : ''}

      <div class="usage-grid">
        ${entries.map(([name, u]) => renderUsageCard(name, u)).join('')}
      </div>

      <div class="usage-explainer">
        <h3>How automatic switching works</h3>
        <div class="explainer-steps">
          <div class="step">
            <div class="step-num">1</div>
            <div class="step-text">You send a message. FreeRouter picks the highest-priority available provider (Ollama → Groq → OpenRouter…)</div>
          </div>
          <div class="step">
            <div class="step-num">2</div>
            <div class="step-text">The provider responds and includes rate limit headers showing how many requests remain.</div>
          </div>
          <div class="step">
            <div class="step-num">3</div>
            <div class="step-text">If remaining drops below 10%, that provider is soft-limited and skipped on next request.</div>
          </div>
          <div class="step">
            <div class="step-num">4</div>
            <div class="step-text">If a provider returns HTTP 429 (rate limit exceeded), it's hard-limited and skipped for 60 seconds, then auto-retried.</div>
          </div>
          <div class="step">
            <div class="step-num">5</div>
            <div class="step-text">Next request automatically goes to the next provider in priority order. You never see an error.</div>
          </div>
        </div>
      </div>
    `;
  } catch (e) {
    panel.innerHTML = `<div class="error-box">Failed to load usage: ${escapeHtml(e.message)}</div>`;
  }
}

function renderUsageCard(name, u) {
  const pct = u.used_pct || 0;
  const barColor = pct >= 90 ? 'bar-danger' : pct >= 70 ? 'bar-warn' : 'bar-ok';

  let statusBadge = '';
  if (u.is_hard_limited) {
    statusBadge = '<span class="badge badge-err">rate limited — resets in ~60s</span>';
  } else if (u.is_soft_limited) {
    statusBadge = '<span class="badge badge-warn">near limit — switching soon</span>';
  } else if (u.has_data) {
    statusBadge = '<span class="badge badge-ok">ok</span>';
  } else {
    statusBadge = '<span class="badge badge-gray">no traffic yet</span>';
  }

  const requestsLine = u.requests_remaining >= 0
    ? `<div class="usage-stat"><span>Requests</span><span>${u.requests_remaining.toLocaleString()} / ${u.requests_limit > 0 ? u.requests_limit.toLocaleString() : '?'} remaining</span></div>`
    : `<div class="usage-stat muted"><span>Requests</span><span>Data appears after first message</span></div>`;

  const tokensLine = u.tokens_remaining >= 0
    ? `<div class="usage-stat"><span>Tokens</span><span>${u.tokens_remaining.toLocaleString()} / ${u.tokens_limit > 0 ? u.tokens_limit.toLocaleString() : '?'} remaining</span></div>`
    : '';

  const lastUpdated = u.last_updated_ago
    ? `<div class="usage-stat muted"><span>Last updated</span><span>${escapeHtml(u.last_updated_ago)}</span></div>`
    : '';

  const defaultModel = u.default_model
    ? `<div class="usage-stat muted"><span>Default model</span><span>${escapeHtml(u.default_model)}</span></div>`
    : '';

  const resetBtn = u.is_hard_limited || u.is_soft_limited
    ? `<button class="btn btn-sm btn-outline" style="margin-top:8px" onclick="resetProvider('${name}')">Clear rate limit</button>`
    : '';

  return `
    <div class="usage-card ${u.is_hard_limited ? 'card-limited' : ''}">
      <div class="usage-header">
        <div>
          <span class="usage-name">${escapeHtml(u.display_name || name)}</span>
          <span class="priority-hint">priority ${u.priority}</span>
        </div>
        ${statusBadge}
      </div>

      <div class="usage-bar-track">
        <div class="usage-bar ${barColor}" style="width: ${Math.min(pct, 100)}%"></div>
      </div>
      <div class="usage-pct-row">
        <span>${pct}% of limit used</span>
        ${pct >= 90 ? '<span class="text-err">switching to next provider</span>' : ''}
        ${pct >= 70 && pct < 90 ? '<span class="text-warn">approaching limit</span>' : ''}
      </div>

      <div class="usage-stats">
        ${requestsLine}
        ${tokensLine}
        ${defaultModel}
        ${lastUpdated}
      </div>

      ${resetBtn}
    </div>
  `;
}

async function resetProvider(name) {
  try {
    await apiFetch(`/providers/${name}/reset`, { method: 'POST' });
    showToast(`Rate limit cleared for ${name}`, 'success');
    loadUsage();
  } catch (e) {
    showToast(`Failed: ${e.message}`, 'error');
  }
}
