/**
 * providers.js — Providers tab: list, configure API keys, health check.
 *
 * Context: Handles the Providers tab UI. Fetches provider list from
 * /api/providers, lets user save API keys, and runs health checks.
 *
 * Functions: loadProviders(), saveKey(name), testProvider(name)
 * Depends on: ui.js (apiFetch, showToast, escapeHtml)
 */

async function loadProviders() {
  const panel = document.getElementById('tab-providers');
  panel.innerHTML = '<div class="loading">Loading providers…</div>';

  try {
    const data = await apiFetch('/providers');
    const providers = data.providers || [];

    panel.innerHTML = `
      <div class="section-header">
        <h2>AI Providers</h2>
        <p class="muted">Add API keys to enable cloud providers. Ollama works without a key if running locally.</p>
      </div>
      <div class="provider-grid">
        ${providers.map(p => renderProvider(p)).join('')}
      </div>
    `;
  } catch (e) {
    panel.innerHTML = `<div class="error-box">Failed to load providers: ${escapeHtml(e.message)}</div>`;
  }
}

function renderProvider(p) {
  const statusBadge = p.is_configured
    ? '<span class="badge badge-ok">configured</span>'
    : (p.requires_auth ? '<span class="badge badge-warn">no key</span>' : '<span class="badge badge-ok">local</span>');

  const keyInput = p.requires_auth ? `
    <div class="key-row">
      <input type="password" id="key-${p.name}" placeholder="Enter API key…" class="key-input"
             onkeydown="if(event.key==='Enter') saveKey('${p.name}')">
      <button class="btn btn-sm" onclick="saveKey('${p.name}')">Save</button>
    </div>
    <a href="${escapeHtml(p.signup_url)}" target="_blank" class="link-small">Get a free key →</a>
  ` : `<p class="muted small">No API key needed. Make sure Ollama is running: <code>ollama serve</code></p>`;

  return `
    <div class="provider-card" id="pcard-${p.name}">
      <div class="provider-header">
        <div>
          <span class="provider-name">${escapeHtml(p.display_name)}</span>
          ${statusBadge}
        </div>
        <button class="btn btn-sm btn-outline" onclick="testProvider('${p.name}')">Test</button>
      </div>
      ${keyInput}
      <div id="pstatus-${p.name}" class="provider-status"></div>
    </div>
  `;
}

async function saveKey(name) {
  const input = document.getElementById(`key-${name}`);
  const key = input.value.trim();
  if (!key) { showToast('Please enter an API key', 'error'); return; }

  try {
    await apiFetch(`/providers/${name}/key`, {
      method: 'POST',
      body: JSON.stringify({ api_key: key }),
    });
    showToast(`API key saved for ${name}`, 'success');
    input.value = '';
    loadProviders();
  } catch (e) {
    showToast(`Failed to save key: ${e.message}`, 'error');
  }
}

async function testProvider(name) {
  const statusEl = document.getElementById(`pstatus-${name}`);
  statusEl.innerHTML = '<span class="muted">Testing…</span>';
  try {
    const data = await apiFetch(`/providers/${name}/test`, { method: 'POST' });
    statusEl.innerHTML = data.ok
      ? `<span class="text-ok">✓ ${escapeHtml(data.message)}</span>`
      : `<span class="text-err">✗ ${escapeHtml(data.message)}</span>`;
  } catch (e) {
    statusEl.innerHTML = `<span class="text-err">✗ ${escapeHtml(e.message)}</span>`;
  }
}
