/**
 * providers.js — Provider management with inline API key saving.
 * Uses freerouter internals directly — no need to open :8080.
 */

async function initProviders() {
  const el = document.getElementById('tab-providers');
  el.innerHTML = `
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">LLM Providers</h2>
        <button class="btn btn-outline btn-sm" onclick="refreshProviders()">⟳ Refresh</button>
      </div>
      <p style="color:var(--text-muted);font-size:12px;margin-bottom:14px">
        FreeRouter routes to the best available provider automatically.
        Add your API keys below — keys are saved to <code>freerouter/.env</code>.
      </p>
      <div id="providers-list"></div>
    </div>
    <div class="card">
      <div class="card-header"><h2 class="card-title">API Usage Today</h2></div>
      <div id="usage-table"></div>
    </div>`;
  await refreshProviders();
}

async function refreshProviders() {
  const list = document.getElementById('providers-list');
  try {
    const data = await api('/api/providers/');
    const providers = data.providers || (Array.isArray(data) ? data : []);
    if (!providers.length) {
      list.innerHTML = `<div class="empty-state"><div class="icon">🔌</div>
        <div class="message">${escHtml(data.error||'No providers')}</div></div>`;
      return;
    }
    list.innerHTML = providers.map(p => `
      <div class="provider-card" style="flex-direction:column;align-items:stretch;gap:10px">
        <div style="display:flex;align-items:center;gap:10px">
          ${statusDot(p.is_configured ? 'online' : 'unknown')}
          <div style="flex:1">
            <div class="provider-name">${escHtml(p.display_name||p.name)}</div>
            <div class="provider-model">${escHtml(p.default_model||'')}</div>
          </div>
          ${p.is_configured
            ? `<button class="btn btn-outline btn-sm" onclick="testProvider('${p.name}')">Test</button>`
            : `<a href="${escHtml(p.signup_url||'#')}" target="_blank" class="btn btn-outline btn-sm" style="font-size:11px">Get key</a>`}
        </div>
        ${p.requires_auth ? `
        <div style="display:flex;gap:6px">
          <input type="password" id="key-${p.name}" class="form-input"
                 placeholder="${p.is_configured ? '••••••••• (key set)' : 'Paste API key…'}"
                 style="flex:1;font-size:12px">
          <button class="btn btn-primary btn-sm" onclick="saveKey('${p.name}')">Save</button>
        </div>` : `<div style="font-size:11px;color:var(--text-muted)">No key needed (local)</div>`}
      </div>`).join('');
  } catch (e) {
    list.innerHTML = `<div class="empty-state"><div class="icon">❌</div>
      <div class="message">Cannot load providers: ${escHtml(e.message)}</div></div>`;
  }

  // Usage stats
  try {
    const usage = await api('/api/providers/usage');
    const el = document.getElementById('usage-table');
    const fr = usage.freerouter || {};
    const pip = usage.pipeline || {};
    const all = {...fr, ...pip};
    const entries = Object.entries(all).filter(([,v]) => (v.requests||0) > 0);
    el.innerHTML = entries.length
      ? `<table class="data-table"><thead><tr>
          <th>Provider</th><th>Requests</th><th>Usage %</th><th>Rate limited</th>
        </tr></thead><tbody>
          ${entries.map(([k,v]) => `<tr>
            <td>${escHtml(k)}</td>
            <td>${v.requests||0}</td>
            <td>${v.requests_used_pct||0}%</td>
            <td>${v.rate_limited
              ? `<button class="btn btn-outline btn-sm" onclick="resetProv('${k}')">Reset</button>`
              : '—'}</td>
          </tr>`).join('')}
        </tbody></table>`
      : '<p style="color:var(--text-muted);font-size:12px">No usage recorded yet</p>';
  } catch {}
}

async function saveKey(name) {
  const input = document.getElementById(`key-${name}`);
  const key = input?.value?.trim();
  if (!key) { showToast('Enter an API key first', 'warning'); return; }
  try {
    await api(`/api/providers/${name}/key`, {method:'POST', body:{api_key:key}});
    if (input) input.value = '';
    showToast(`${name} key saved`, 'success');
    await refreshProviders();
  } catch (e) { showToast(`Save failed: ${e.message}`, 'error'); }
}

async function testProvider(name) {
  showToast(`Testing ${name}…`, 'info', 2000);
  try {
    const r = await api(`/api/providers/${name}/test`, {method:'POST'});
    showToast(`${name}: ${r.ok ? '✓ ' : '✗ '}${r.message}`, r.ok ? 'success' : 'error', 5000);
  } catch (e) { showToast(`Test failed: ${e.message}`, 'error'); }
}

async function resetProv(name) {
  try {
    await api(`/api/providers/${name}/reset`, {method:'POST'});
    showToast(`${name} rate limit cleared`, 'success');
    await refreshProviders();
  } catch (e) { showToast(`Reset failed: ${e.message}`, 'error'); }
}
