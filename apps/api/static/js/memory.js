/** memory.js — Zep agent memory browser. */

async function initMemory() {
  const el = document.getElementById('tab-memory');
  el.innerHTML = `
    <div class="card">
      <div class="card-header"><h2 class="card-title">Agent Memory (Zep)</h2>
        <button class="btn btn-outline btn-sm" onclick="refreshMemory()">⟳ Refresh</button></div>
      <div style="display:flex;gap:8px;margin-bottom:14px">
        <input id="mem-search" class="form-input" placeholder="Search memory…" style="flex:1">
        <button class="btn btn-primary btn-sm" onclick="searchMem()">Search</button>
      </div>
      <div id="mem-results"></div>
      <div id="mem-sessions"></div>
    </div>`;
  await refreshMemory();
}

async function refreshMemory() {
  try {
    const data = await api('/api/memory/sessions');
    const el = document.getElementById('mem-sessions');
    if (data.error) {
      el.innerHTML = `<div class="empty-state"><div class="icon">🧠</div>
        <div class="message">${escHtml(data.error)}</div>
        <div class="help">${escHtml(data.help||'Set ZEP_API_KEY in .env')}</div></div>`;
      return;
    }
    const sessions = data.sessions || data || [];
    el.innerHTML = sessions.length
      ? `<h4 style="color:var(--text-secondary);font-size:12px;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px">Sessions</h4>` +
        sessions.map(s => `
          <div class="provider-card" style="cursor:pointer" onclick="viewSession('${s.session_id}')">
            <div>
              <div class="provider-name">${escHtml(s.session_id)}</div>
              <div class="provider-model">${escHtml(s.metadata?.session_type||'—')}</div>
              <div class="provider-usage">${fmtDate(s.created_at)}</div>
            </div>
          </div>`).join('')
      : `<div class="empty-state"><div class="icon">🧠</div>
          <div class="message">No memory sessions yet</div>
          <div class="help">Created when agents process tasks</div></div>`;
  } catch { document.getElementById('mem-sessions').innerHTML = `<div class="empty-state"><div class="icon">❌</div><div class="message">Cannot load sessions</div></div>`; }
}

async function viewSession(id) {
  try {
    const [mem, facts] = await Promise.all([api(`/api/memory/sessions/${id}`), api(`/api/memory/facts/${id}`)]);
    showModal(`
      <div style="display:flex;justify-content:space-between;margin-bottom:16px">
        <h3 style="color:var(--text-primary)">${escHtml(id)}</h3>
        <button class="btn btn-outline btn-sm" onclick="hideModal()">✕</button>
      </div>
      <h4 style="color:var(--text-secondary);margin-bottom:6px">Summary</h4>
      <p style="color:var(--text-primary)">${escHtml(mem.summary||'No summary')}</p>
      <h4 style="color:var(--text-secondary);margin:14px 0 6px">Facts</h4>
      <ul style="color:var(--text-primary);padding-left:16px">${(facts||[]).map(f=>`<li>${escHtml(f)}</li>`).join('')||'<li>No facts</li>'}</ul>`);
  } catch (e) { showToast(`Cannot load: ${e.message}`, 'error'); }
}

async function searchMem() {
  const q = document.getElementById('mem-search').value;
  if (!q) return;
  try {
    const results = await api(`/api/memory/search?query=${encodeURIComponent(q)}`, {method:'POST'});
    const el = document.getElementById('mem-results');
    el.innerHTML = results.length
      ? results.map(r => `<div class="provider-card"><div>
          <div class="provider-name">${escHtml((r.content||'').slice(0,100))}</div>
          <div class="provider-usage">Relevance: ${((r.relevance||0)*100).toFixed(0)}%</div>
        </div></div>`).join('')
      : '<p style="color:var(--text-muted)">No results</p>';
  } catch (e) { showToast(`Search failed: ${e.message}`, 'error'); }
}
