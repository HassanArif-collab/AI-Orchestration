/** analytics.js — YouTube channel analytics. */

async function initAnalytics() {
  const el = document.getElementById('tab-analytics');
  el.innerHTML = `
    <div class="card"><div class="card-header"><h2 class="card-title">Channel Stats</h2>
      <button class="btn btn-outline btn-sm" onclick="saveSnap()">📸 Snapshot</button></div>
      <div id="ch-stats"></div></div>
    <div class="card"><div class="card-header"><h2 class="card-title">Recent Videos</h2>
      <button class="btn btn-outline btn-sm" onclick="refreshAnalytics()">⟳ Refresh</button></div>
      <div id="vid-table"></div></div>
    <div class="card"><div class="card-header"><h2 class="card-title">Competitors</h2></div>
      <div id="comp-table"></div></div>`;
  await refreshAnalytics();
}

async function refreshAnalytics() {
  try {
    const s = await api('/api/analytics/channel');
    document.getElementById('ch-stats').innerHTML = s.error
      ? `<p style="color:var(--text-muted)">${escHtml(s.error)}</p>`
      : `<div style="display:flex;gap:32px;flex-wrap:wrap">
          ${[['Subscribers',s.subscriber_count],['Total Views',s.total_views],['Videos',s.video_count]]
            .map(([l,v])=>`<div><div style="font-size:28px;font-weight:600;color:var(--text-primary)">${v?.toLocaleString()||'—'}</div>
            <div style="color:var(--text-muted);font-size:12px">${l}</div></div>`).join('')}</div>`;
  } catch { document.getElementById('ch-stats').innerHTML = `<p style="color:var(--text-muted)">Set YOUTUBE_API_KEY in .env</p>`; }

  try { renderVidTable('vid-table', await api('/api/analytics/videos')); }
  catch { document.getElementById('vid-table').innerHTML = `<p style="color:var(--text-muted)">Cannot load videos</p>`; }

  try {
    // Backend returns {videos: [...]} — extract the array
    const compData = await api('/api/analytics/competitors');
    renderVidTable('comp-table', compData.videos || compData || []);
  }
  catch { document.getElementById('comp-table').innerHTML = `<p style="color:var(--text-muted)">No competitor data</p>`; }
}

function renderVidTable(id, videos) {
  const el = document.getElementById(id);
  if (!videos?.length) { el.innerHTML = `<p style="color:var(--text-muted)">No videos found</p>`; return; }
  el.innerHTML = `<table class="data-table"><thead><tr><th>Title</th><th>Views</th><th>Likes</th><th>Published</th></tr></thead><tbody>
    ${videos.map(v=>`<tr>
      <td><a href="https://youtube.com/watch?v=${v.video_id}" target="_blank">${escHtml((v.title||'').slice(0,60))}</a></td>
      <td>${v.views?.toLocaleString()||'—'}</td><td>${v.likes?.toLocaleString()||'—'}</td>
      <td>${fmtDate(v.published_at)}</td></tr>`).join('')}
  </tbody></table>`;
}

async function saveSnap() {
  try {
    const r = await api('/api/analytics/snapshot', {method:'POST'});
    showToast(`Saved: ${r.filepath}`, 'success');
  } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}
