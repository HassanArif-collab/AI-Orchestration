/** settings.js — System health and configuration. */

async function initSettings() {
  const el = document.getElementById('tab-settings');
  el.innerHTML = `
    <div class="card"><div class="card-header"><h2 class="card-title">System Health</h2>
      <button class="btn btn-outline btn-sm" onclick="refreshSettings()">⟳ Check</button></div>
      <div id="health-table"></div></div>
    <div class="card"><div class="card-header"><h2 class="card-title">Configuration</h2></div>
      <div id="config-table"></div></div>
    <div class="card"><div class="card-header"><h2 class="card-title">Startup Commands</h2></div>
      <div id="cmds-list"></div></div>`;
  await refreshSettings();
}

async function refreshSettings() {
  try {
    const s = await api('/api/settings/status');
    const dot = s.overall==='healthy'?'online':s.overall==='degraded'?'warning':'offline';
    document.getElementById('health-table').innerHTML = `
      <div style="margin-bottom:12px">${statusDot(dot)}
        <strong style="color:var(--text-primary);margin-left:6px">${(s.overall||'unknown').toUpperCase()}</strong></div>
      <table class="data-table"><thead><tr><th>Component</th><th>Status</th><th>Details</th></tr></thead><tbody>
        ${Object.entries(s.components||{}).map(([k,v])=>`<tr>
          <td class="mono" style="font-size:12px">${k}</td>
          <td>${statusDot(v.status==='online'||v.status==='ok'?'online':v.status==='not_configured'||v.status==='not_scaffolded'?'unknown':'offline')} ${v.status}</td>
          <td style="font-size:11px;color:var(--text-muted)">${escHtml(v.fix||v.url||v.path||String(v.count||''))}</td>
        </tr>`).join('')}
      </tbody></table>`;
  } catch { document.getElementById('health-table').innerHTML=`<p style="color:var(--accent-error)">Cannot reach API</p>`; }

  try {
    const cfg = await api('/api/settings/');
    document.getElementById('config-table').innerHTML = `
      <table class="data-table"><tbody>
        ${Object.entries(cfg).map(([k,v])=>`<tr>
          <td class="mono" style="font-size:12px">${k}</td>
          <td>${typeof v==='boolean'?(v?'✓ Configured':'Not set'):escHtml(String(v))}</td>
        </tr>`).join('')}
      </tbody></table>`;
  } catch {}

  try {
    const cmds = await api('/api/settings/commands');
    document.getElementById('cmds-list').innerHTML = Object.entries(cmds).map(([k,v])=>`
      <div class="provider-card">
        <div>
          <div class="provider-name">${k}</div>
          <code>${escHtml(v)}</code>
        </div>
      </div>`).join('');
  } catch {}
}
