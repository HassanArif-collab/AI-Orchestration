/** visual.js — Radiant shaders, Remotion templates, asset manifests. */

async function initVisual() {
  const el = document.getElementById('tab-visual');
  el.innerHTML = `
    <div class="card"><div class="card-header"><h2 class="card-title">Asset Manifests</h2></div>
      <div id="manifest-list"></div></div>
    <div class="card"><div class="card-header"><h2 class="card-title">Radiant Shaders</h2>
      <button class="btn btn-outline btn-sm" onclick="refreshVisual()">⟳ Refresh</button></div>
      <p style="color:var(--text-muted);font-size:12px;margin-bottom:12px">Animated canvas backgrounds. Click to preview.</p>
      <div id="shader-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px"></div></div>
    <div class="card"><div class="card-header"><h2 class="card-title">Remotion Templates</h2></div>
      <div id="remotion-list"></div></div>`;
  await refreshVisual();
}

async function refreshVisual() {
  try {
    const m = await api('/api/visual/manifests');
    document.getElementById('manifest-list').innerHTML = m.length
      ? m.map(x=>`<div class="provider-card"><div>
          <div class="provider-name">${escHtml(x.video_title)}</div>
          <div class="provider-usage">${x.complete}/${x.total_assets} assets</div>
        </div></div>`).join('')
      : '<p style="color:var(--text-muted)">No assets created yet</p>';
  } catch {}

  try {
    const shaders = await api('/api/visual/radiant/shaders');
    const grid = document.getElementById('shader-grid');
    grid.innerHTML = shaders.length
      ? shaders.map(s=>`<div class="provider-card" style="cursor:pointer;flex-direction:column;text-align:center"
          onclick="previewShader('${escHtml(s.name)}')">
          <div class="provider-name">${escHtml(s.name)}</div></div>`).join('')
      : `<div class="empty-state" style="grid-column:1/-1"><div class="icon">🎨</div>
          <div class="message">Radiant not installed</div>
          <div class="help"><code>RadiantManager().setup()</code></div></div>`;
  } catch {}

  try {
    const t = await api('/api/visual/remotion/templates');
    document.getElementById('remotion-list').innerHTML = `<div style="display:flex;flex-wrap:wrap;gap:8px">
      ${t.map(x=>`<span style="background:var(--bg-tertiary);padding:5px 12px;border-radius:var(--radius);font-size:12px;color:var(--text-primary)">${escHtml(x)}</span>`).join('')}</div>`;
  } catch {}
}

function previewShader(name) {
  showModal(`
    <div style="display:flex;justify-content:space-between;margin-bottom:12px">
      <h3 style="color:var(--text-primary)">${escHtml(name)}</h3>
      <button class="btn btn-outline btn-sm" onclick="hideModal()">✕</button>
    </div>
    <iframe src="/api/visual/radiant/preview/${encodeURIComponent(name)}"
            style="width:100%;height:360px;border:1px solid var(--border);border-radius:var(--radius)"></iframe>
    <div style="margin-top:10px;display:flex;align-items:center;gap:8px">
      <label class="form-label" style="white-space:nowrap;margin:0">Color scheme</label>
      <select class="form-input" style="width:auto" onchange="changeShader(this.value)">
        <option value="none">Amber (default)</option>
        <option value="grayscale(1)">Mono</option>
        <option value="hue-rotate(175deg)">Blue</option>
        <option value="hue-rotate(300deg) saturate(1.1)">Rose</option>
        <option value="hue-rotate(90deg) saturate(1.2)">Emerald</option>
      </select>
    </div>`);
}

function changeShader(filter) {
  const iframe = document.querySelector('#modal-content iframe');
  if (iframe) iframe.style.filter = filter;
}
