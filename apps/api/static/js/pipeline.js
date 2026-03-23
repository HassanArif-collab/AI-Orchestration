/**
 * pipeline.js — Pipeline management: kanban board, run detail, human gates.
 */

const STAGE_ICONS = {
  trend_analysis:'🔍', human_topic_approval:'🙋', research:'📚',
  script_writing:'✍️', visual_planning:'🎨', human_review:'👁️',
  asset_creation:'🏗️', seo:'🏷️', publish:'🚀',
};
const STAGE_LABELS = {
  trend_analysis:'Trend', human_topic_approval:'Pick Topic', research:'Research',
  script_writing:'Script', visual_planning:'Visual', human_review:'Review',
  asset_creation:'Assets', seo:'SEO', publish:'Publish',
};
const STAGE_ORDER = ['trend_analysis','human_topic_approval','research','script_writing',
                     'visual_planning','seo','human_review','asset_creation','publish'];
const STATUS_CLASS = {complete:'complete',running:'running',waiting_human:'waiting',error:'error',pending:'pending'};

let _viewMode = 'board'; // 'board' | 'list'

async function initPipeline() {
  const el = document.getElementById('tab-pipeline');
  el.innerHTML = `
    <div class="card">
      <div class="card-header">
        <h2 class="card-title">Pipeline Runs</h2>
        <div style="display:flex;gap:8px;align-items:center">
          <div style="display:flex;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">
            <button id="view-board" class="btn btn-sm" style="border-radius:0;background:var(--accent-primary);color:#fff" onclick="setView('board')">Board</button>
            <button id="view-list"  class="btn btn-sm" style="border-radius:0" onclick="setView('list')">List</button>
          </div>
          <button class="btn btn-primary btn-sm" onclick="startNewPipeline()">+ New Run</button>
        </div>
      </div>
      <div id="pipeline-body"></div>
    </div>`;
  await refreshPipeline();
}

function setView(mode) {
  _viewMode = mode;
  document.getElementById('view-board').style.background = mode === 'board' ? 'var(--accent-primary)' : '';
  document.getElementById('view-board').style.color      = mode === 'board' ? '#fff' : '';
  document.getElementById('view-list').style.background  = mode === 'list'  ? 'var(--accent-primary)' : '';
  document.getElementById('view-list').style.color       = mode === 'list'  ? '#fff' : '';
  refreshPipeline();
}

async function refreshPipeline() {
  try {
    const runs = await api('/api/pipeline/runs');
    const body = document.getElementById('pipeline-body');
    if (!runs || runs.length === 0) {
      body.innerHTML = `<div class="empty-state"><div class="icon">📋</div>
        <div class="message">No pipeline runs yet</div>
        <div class="help">Click "+ New Run" to produce your first video</div></div>`;
      return;
    }
    if (_viewMode === 'board') renderBoard(body, runs);
    else renderList(body, runs);
  } catch (e) {
    document.getElementById('pipeline-body').innerHTML =
      `<div class="empty-state"><div class="icon">📋</div>
       <div class="message">No runs yet</div>
       <div class="help">Start your first pipeline run</div></div>`;
  }
}

function renderBoard(container, runs) {
  const cols = {
    running:  { label: 'Running',  runs: [] },
    waiting:  { label: 'Waiting',  runs: [] },
    complete: { label: 'Complete', runs: [] },
    error:    { label: 'Error',    runs: [] },
  };
  for (const r of runs) {
    const s = r.status;
    if (s === 'running') cols.running.runs.push(r);
    else if (s === 'waiting_human') cols.waiting.runs.push(r);
    else if (s === 'complete') cols.complete.runs.push(r);
    else cols.error.runs.push(r);
  }

  container.innerHTML = `<div class="kanban-board">` +
    Object.entries(cols).map(([key, col]) => `
      <div class="kanban-col">
        <div class="kanban-col-header ${key}">${col.label} <span style="opacity:.5">${col.runs.length}</span></div>
        <div class="kanban-body">
          ${col.runs.length ? col.runs.map(r => `
            <div class="run-card" onclick="loadRunDetail('${r.run_id}')">
              <div class="run-card-title">${escHtml(r.video_title || 'New Run')}</div>
              <div class="run-card-stage">${escHtml(r.current_stage || '—')}</div>
              <div class="run-card-meta">${r.run_id.slice(0,8)}</div>
            </div>`).join('') :
            `<div style="padding:12px;font-size:11px;color:var(--text-muted);text-align:center">Empty</div>`}
        </div>
      </div>`).join('') + `</div>`;
}

function renderList(container, runs) {
  container.innerHTML = runs.map(r => `
    <div class="card" style="cursor:pointer;margin-bottom:10px" onclick="loadRunDetail('${r.run_id}')">
      <div class="card-header" style="margin-bottom:10px">
        <span class="card-title">${escHtml(r.video_title || 'Untitled')}
          <span class="mono" style="font-size:11px;color:var(--text-muted);margin-left:8px">${r.run_id.slice(0,8)}</span>
        </span>
        ${statusDot(STATUS_CLASS[r.status] || 'unknown')}
      </div>
      <div class="pipeline-graph">${renderMiniGraph(r.stages)}</div>
    </div>`).join('');
}

function renderMiniGraph(stages = {}) {
  return STAGE_ORDER.map((s, i) => {
    const info = stages[s] || {status:'pending'};
    const cls = STATUS_CLASS[info.status] || 'pending';
    const sep = i > 0 ? `<span class="pipeline-arrow">›</span>` : '';
    return `${sep}<div class="pipeline-stage ${cls}" title="${s}" style="min-width:60px;padding:6px 8px">
      <div class="stage-icon">${STAGE_ICONS[s]||'•'}</div>
      <div class="stage-name" style="font-size:10px">${STAGE_LABELS[s]||s}</div>
    </div>`;
  }).join('');
}

async function loadRunDetail(runId) {
  try {
    const run = await api(`/api/pipeline/runs/${runId}`);
    showRunDetail(run);
  } catch (e) {
    showToast(`Failed to load run: ${e.message}`, 'error');
  }
}

function showRunDetail(run) {
  const stages = run.stages || {};
  const isWaiting = run.status === 'waiting_human';

  // Approval UI
  let approvalHtml = '';
  if (isWaiting) {
    if (run.current_stage === 'human_topic_approval') {
      const ideas = stages.trend_analysis?.output || [];
      const ideasArr = Array.isArray(ideas) ? ideas : [];
      approvalHtml = `
        <div class="card" style="border-color:var(--accent-warning);margin-bottom:12px">
          <div class="card-header"><h3 style="color:var(--accent-warning)">🙋 Pick a topic to research</h3></div>
          <div class="idea-cards">
            ${ideasArr.map((idea, i) => `
              <div class="idea-card" onclick="approveTopicSelection('${run.run_id}', ${i}, ${JSON.stringify(idea).replace(/"/g,'&quot;')})">
                <div class="idea-title">${escHtml(idea.title||'Idea '+(i+1))}</div>
                <div class="idea-angle">${escHtml(idea.angle||'')}</div>
                <div class="idea-score">Viral score: ${idea.viral_score||'?'}/10</div>
                <div class="idea-bar-track"><div class="idea-bar" style="width:${(idea.viral_score||5)*10}%"></div></div>
              </div>`).join('') ||
              `<p style="color:var(--text-muted)">No ideas available</p>`}
          </div>
        </div>`;
    } else if (run.current_stage === 'human_review') {
      approvalHtml = `
        <div class="card" style="border-color:var(--accent-warning);margin-bottom:12px">
          <div class="card-header"><h3 style="color:var(--accent-warning)">👁️ Review script & visual plan</h3></div>
          <div class="form-group">
            <label class="form-label">Feedback (optional)</label>
            <textarea id="review-feedback" class="form-input" placeholder="Any changes needed?"></textarea>
          </div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-success" onclick="approveReview('${run.run_id}')">✓ Approve</button>
            <button class="btn btn-danger"  onclick="rejectReview('${run.run_id}')">✗ Reject & Revise</button>
          </div>
        </div>`;
    }
  }

  // Stage outputs (expandable)
  const outputsHtml = STAGE_ORDER
    .filter(s => stages[s]?.output)
    .map(s => `
      <div style="margin-bottom:8px;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">
        <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;cursor:pointer;background:var(--bg-tertiary)"
             onclick="this.nextElementSibling.classList.toggle('open')">
          <span>${STAGE_ICONS[s]} ${STAGE_LABELS[s]}</span>
          <span style="color:var(--text-muted);font-size:12px">▾</span>
        </div>
        <div class="expandable" style="padding:0">
          <pre style="margin:0;border:none;border-radius:0;max-height:300px;overflow-y:auto">${escHtml(JSON.stringify(stages[s].output,null,2))}</pre>
        </div>
      </div>`).join('');

  // Feedback loop
  const feedbackHtml = stages.script_writing?.status === 'complete' ? `
    <div class="card" style="margin-top:12px">
      <div class="card-title" style="margin-bottom:10px">🔄 Request revision</div>
      <div class="form-group">
        <label class="form-label">Send script back to research with feedback:</label>
        <textarea id="feedback-text" class="form-input" placeholder="e.g. Need more data on Pakistan's GDP growth rate"></textarea>
      </div>
      <button class="btn btn-outline btn-sm" onclick="sendFeedback('${run.run_id}')">Send to Researcher</button>
    </div>` : '';

  showModal(`
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2 style="font-size:16px;color:var(--text-primary)">${escHtml(run.video_title||'Pipeline Run')}</h2>
      <div style="display:flex;gap:8px">
        <button class="btn btn-danger btn-sm" onclick="deleteRun('${run.run_id}')">Delete</button>
        <button class="btn btn-outline btn-sm" onclick="hideModal()">✕</button>
      </div>
    </div>
    <div class="pipeline-graph" style="margin-bottom:16px">${renderMiniGraph(run.stages)}</div>
    ${approvalHtml}
    ${outputsHtml}
    ${feedbackHtml}
  `);
}

async function startNewPipeline() {
  showModal(`
    <h3 style="color:var(--text-primary);margin-bottom:16px">Start new pipeline</h3>
    <div class="form-group">
      <label class="form-label">Topic (optional — leave blank for trend analysis)</label>
      <input type="text" id="new-topic" class="form-input"
             placeholder="e.g. Why Pakistan's AI policy matters">
    </div>
    <div style="display:flex;gap:8px;justify-content:flex-end">
      <button class="btn btn-outline" onclick="hideModal()">Cancel</button>
      <button class="btn btn-primary" onclick="confirmStart()">Start</button>
    </div>`);
}

async function confirmStart() {
  const topic = document.getElementById('new-topic').value;
  hideModal();
  try {
    const r = await api('/api/pipeline/runs', {method:'POST', body:{topic}});
    showToast(`Pipeline started: ${r.run_id.slice(0,8)}`, 'success');
    await refreshPipeline();
  } catch (e) {
    showToast(`Failed: ${e.message}`, 'error');
  }
}

async function approveTopicSelection(runId, i, idea) {
  try {
    await api(`/api/pipeline/runs/${runId}/approve`, {method:'POST', body:{selection:idea}});
    hideModal();
    showToast('Topic selected — research starting…', 'success');
    const badge = document.getElementById('pipeline-badge');
    const n = Math.max(0, parseInt(badge.textContent||'1')-1);
    badge.textContent = n;
    if (n===0) badge.classList.add('hidden');
    await refreshPipeline();
  } catch (e) { showToast(`Approval failed: ${e.message}`, 'error'); }
}

async function approveReview(runId) {
  const feedback = document.getElementById('review-feedback')?.value||'';
  try {
    await api(`/api/pipeline/runs/${runId}/approve`, {method:'POST', body:{feedback}});
    hideModal();
    showToast('Approved — assets generating…', 'success');
    await refreshPipeline();
  } catch (e) { showToast(`Approval failed: ${e.message}`, 'error'); }
}

async function rejectReview(runId) {
  const feedback = document.getElementById('review-feedback')?.value||'';
  if (!feedback) { showToast('Please add feedback before rejecting', 'warning'); return; }
  try {
    await api(`/api/pipeline/runs/${runId}/reject`, {method:'POST', body:{feedback}});
    hideModal();
    showToast('Sent back for revision', 'info');
    await refreshPipeline();
  } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}

async function sendFeedback(runId) {
  const feedback = document.getElementById('feedback-text')?.value||'';
  if (!feedback) { showToast('Please add feedback', 'warning'); return; }
  try {
    await api(`/api/pipeline/runs/${runId}/feedback`, {
      method:'POST', body:{from_stage:'script_writing',to_stage:'research',feedback}});
    hideModal();
    showToast('Feedback sent to researcher', 'info');
  } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}

async function deleteRun(runId) {
  if (!confirm('Delete this pipeline run?')) return;
  try {
    await api(`/api/pipeline/runs/${runId}`, {method:'DELETE'});
    hideModal();
    showToast('Run deleted', 'info');
    await refreshPipeline();
  } catch (e) { showToast(`Delete failed: ${e.message}`, 'error'); }
}
