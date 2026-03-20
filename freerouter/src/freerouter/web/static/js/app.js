/**
 * app.js — Usage tab loader. (Most logic is in providers.js, chat.js, ui.js)
 *
 * Context: Handles the Usage tab only. All other tab logic is in dedicated files.
 * This file exists so the HTML only needs one <script> import entry point
 * in addition to the module files.
 *
 * Depends on: ui.js (apiFetch, escapeHtml)
 */

async function loadUsage() {
  const panel = document.getElementById('tab-usage');
  panel.innerHTML = '<div class="loading">Loading usage…</div>';

  try {
    const data = await apiFetch('/usage');
    const usage = data.usage || {};
    const entries = Object.entries(usage);

    if (entries.length === 0) {
      panel.innerHTML = `
        <div class="section-header"><h2>Usage</h2></div>
        <div class="empty-state">No usage data yet. Send some messages in the Chat tab first.</div>
      `;
      return;
    }

    panel.innerHTML = `
      <div class="section-header">
        <h2>Rate Limit Usage</h2>
        <p class="muted">Updated after each request. Auto-switches providers before hitting limits.</p>
      </div>
      <div class="usage-grid">
        ${entries.map(([name, u]) => renderUsageCard(name, u)).join('')}
      </div>
    `;
  } catch (e) {
    panel.innerHTML = `<div class="error-box">Failed to load usage: ${escapeHtml(e.message)}</div>`;
  }
}

function renderUsageCard(name, u) {
  const pct = u.used_pct || 0;
  const barColor = pct >= 90 ? 'bar-danger' : pct >= 70 ? 'bar-warn' : 'bar-ok';
  const status = u.is_hard_limited ? '🔴 rate limited' : u.is_soft_limited ? '🟡 near limit' : '🟢 ok';

  return `
    <div class="usage-card">
      <div class="usage-header">
        <span class="usage-name">${escapeHtml(name)}</span>
        <span class="usage-status">${status}</span>
      </div>
      <div class="usage-bar-track">
        <div class="usage-bar ${barColor}" style="width: ${Math.min(pct, 100)}%"></div>
      </div>
      <div class="usage-detail">
        ${u.requests_remaining >= 0
          ? `${u.requests_remaining} / ${u.requests_limit || '?'} requests remaining`
          : 'No usage data yet'}
        <span class="pct">${pct}%</span>
      </div>
    </div>
  `;
}
