/**
 * pipeline.js — Pipeline management: kanban board, run detail, human gates.
 */

const STAGE_ICONS = {
  trend_analysis: '🔍', human_topic_approval: '🙋', research: '📚',
  script_writing: '✍️', visual_planning: '🎨', human_review: '👁️',
  asset_creation: '🏗️', seo: '🏷️', publish: '🚀',
};
const STAGE_LABELS = {
  trend_analysis: 'Trend', human_topic_approval: 'Pick Topic', research: 'Research',
  script_writing: 'Script', visual_planning: 'Visual', human_review: 'Review',
  asset_creation: 'Assets', seo: 'SEO', publish: 'Publish',
};
const STAGE_ORDER = ['trend_analysis', 'human_topic_approval', 'research', 'script_writing',
  'visual_planning', 'seo', 'human_review', 'asset_creation', 'publish'];
const STATUS_CLASS = { complete: 'complete', running: 'running', waiting_human: 'waiting', error: 'error', pending: 'pending' };

/**
 * Render artifact data as readable HTML instead of raw JSON.
 * Handles AdaptedScript, Research, Visual Planning, and Trend Analysis outputs.
 */
function renderArtifactHtml(data, stageName) {
  if (!data) return '<div style="color:var(--text-muted);padding:8px">No output</div>';
  
  // Handle string output
  if (typeof data === 'string') {
    return `<div style="padding:8px;white-space:pre-wrap">${escHtml(data.slice(0, 500))}${data.length > 500 ? '...' : ''}</div>`;
  }
  
  // Handle arrays (trend_analysis topic candidates)
  if (Array.isArray(data)) {
    if (data.length === 0) return '<div style="color:var(--text-muted);padding:8px">Empty list</div>';
    return data.slice(0, 5).map((item, i) => `
      <div style="padding:8px;border-bottom:1px solid var(--border)">
        <div style="font-weight:600;margin-bottom:4px">${escHtml(item.title || item.topic_statement || `Item ${i+1}`)}</div>
        <div style="font-size:12px;color:var(--text-secondary)">${escHtml(item.subtitle || item.big_question || '')}</div>
        ${item.viability_total ? `<div style="font-size:11px;color:var(--text-muted);margin-top:4px">Viability: ${item.viability_total}/17</div>` : ''}
      </div>`).join('') + (data.length > 5 ? `<div style="padding:8px;color:var(--text-muted);font-size:11px">... and ${data.length - 5} more</div>` : '');
  }
  
  // Handle objects
  if (typeof data !== 'object') {
    return `<div style="padding:8px">${escHtml(String(data).slice(0, 500))}</div>`;
  }
  
  // AdaptedScript (script_writing) - dual column table
  if (data.entries && Array.isArray(data.entries)) {
    let html = '';
    if (data.adapted_title) {
      html += `<div style="padding:8px;font-weight:600;border-bottom:1px solid var(--border)">${escHtml(data.adapted_title)}</div>`;
    }
    if (data.production_readiness_score !== undefined) {
      html += `<div style="padding:4px 8px;font-size:11px;color:var(--text-muted)">Score: ${data.production_readiness_score.toFixed(1)}%</div>`;
    }
    html += `<table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead><tr style="background:var(--bg-tertiary)">
        <th style="padding:6px;text-align:left;border-bottom:1px solid var(--border)">Narration</th>
        <th style="padding:6px;text-align:left;border-bottom:1px solid var(--border)">Visual</th>
      </tr></thead><tbody>`;
    data.entries.slice(0, 8).forEach((entry, i) => {
      const bg = i % 2 === 0 ? '' : 'background:var(--bg-secondary)';
      html += `<tr style="${bg}">
        <td style="padding:6px;vertical-align:top;border-bottom:1px solid var(--border)">${escHtml(entry.prose || '')}</td>
        <td style="padding:6px;vertical-align:top;border-bottom:1px solid var(--border);color:var(--text-secondary)">${escHtml(entry.visual_direction || '')}</td>
      </tr>`;
    });
    html += '</tbody></table>';
    if (data.entries.length > 8) {
      html += `<div style="padding:4px 8px;color:var(--text-muted);font-size:11px">... and ${data.entries.length - 8} more entries</div>`;
    }
    return html;
  }
  
  // Visual Planning - section briefs
  if (data.section_briefs && Array.isArray(data.section_briefs)) {
    return data.section_briefs.slice(0, 6).map((brief, i) => `
      <div style="padding:6px 8px;border-bottom:1px solid var(--border)">
        <span style="color:var(--accent-primary);font-weight:600">Section ${brief.section_index || i}:</span>
        <span style="color:var(--text-secondary)">${escHtml((brief.sonic_palette || '').slice(0, 60))}</span>
      </div>`).join('') + (data.section_briefs.length > 6 ? `<div style="padding:8px;color:var(--text-muted);font-size:11px">... and ${data.section_briefs.length - 6} more sections</div>` : '');
  }
  
  // Research output - show key fields
  const keyFields = ['topic', 'title', 'summary', 'main_findings', 'key_points', 'source_title'];
  let html = '';
  for (const key of keyFields) {
    if (data[key]) {
      let val = data[key];
      if (Array.isArray(val)) {
        val = val.slice(0, 3).map(v => escHtml(String(v).slice(0, 80))).join('<br>');
      } else {
        val = escHtml(String(val).slice(0, 200));
      }
      html += `<div style="padding:6px 8px;border-bottom:1px solid var(--border)">
        <span style="font-weight:600;color:var(--text-secondary)">${key}:</span> ${val}
      </div>`;
    }
  }
  if (html) return html;
  
  // Fallback: formatted JSON (limited)
  const jsonStr = JSON.stringify(data, null, 2);
  if (jsonStr.length > 800) {
    return `<pre style="margin:0;padding:8px;font-size:11px;white-space:pre-wrap;max-height:200px;overflow:auto">${escHtml(jsonStr.slice(0, 800))}...</pre>`;
  }
  return `<pre style="margin:0;padding:8px;font-size:11px;white-space:pre-wrap;max-height:200px;overflow:auto">${escHtml(jsonStr)}</pre>`;
}

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
  document.getElementById('view-board').style.color = mode === 'board' ? '#fff' : '';
  document.getElementById('view-list').style.background = mode === 'list' ? 'var(--accent-primary)' : '';
  document.getElementById('view-list').style.color = mode === 'list' ? '#fff' : '';
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
    running: { label: 'Running', runs: [] },
    waiting: { label: 'Waiting', runs: [] },
    complete: { label: 'Complete', runs: [] },
    error: { label: 'Error', runs: [] },
  };
  for (const r of runs) {
    const s = r.status;
    if (s === 'running') cols.running.runs.push(r);
    else if (s === 'waiting_human') cols.waiting.runs.push(r);
    else if (s === 'complete') cols.complete.runs.push(r);
    else cols.error.runs.push(r);
  }

  container.innerHTML = `<div class="pipeline-board">` +
    Object.entries(cols).map(([key, col]) => `
      <div class="pipeline-col">
        <div class="pipeline-col-header ${key}">${col.label} <span style="opacity:.5">${col.runs.length}</span></div>
        <div class="pipeline-body">
          ${col.runs.length ? col.runs.map(r => `
            <div class="run-card" onclick="loadRunDetail('${r.run_id}')">
              <div class="run-card-title">${escHtml(r.video_title || 'New Run')}</div>
              <div class="run-card-stage">${escHtml(r.current_stage || '—')}</div>
              <div class="run-card-meta">${r.run_id.slice(0, 8)}</div>
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
          <span class="mono" style="font-size:11px;color:var(--text-muted);margin-left:8px">${r.run_id.slice(0, 8)}</span>
        </span>
        ${statusDot(STATUS_CLASS[r.status] || 'unknown')}
      </div>
      <div class="pipeline-graph">${renderMiniGraph(r.stages)}</div>
    </div>`).join('');
}

function renderMiniGraph(stages = {}) {
  return STAGE_ORDER.map((s, i) => {
    const info = stages[s] || { status: 'pending' };
    const cls = STATUS_CLASS[info.status] || 'pending';
    const sep = i > 0 ? `<span class="pipeline-arrow">›</span>` : '';
    return `${sep}<div class="pipeline-stage ${cls}" title="${s}" style="min-width:60px;padding:6px 8px">
      <div class="stage-icon">${STAGE_ICONS[s] || '•'}</div>
      <div class="stage-name" style="font-size:10px">${STAGE_LABELS[s] || s}</div>
    </div>`;
  }).join('');
}

async function loadRunDetail(runId) {
  try {
    const run = await api(`/api/pipeline/runs/${runId}`);
    const iterationData = await api(`/api/pipeline/runs/${runId}/iterations`).catch(() => ({ iterations: [] }));
    showRunDetail(run, iterationData.iterations || []);
  } catch (e) {
    showToast(`Failed to load run: ${e.message}`, 'error');
  }
}

function _buildErrorBanner(run) {
  if (run.status !== 'error' || !run.error_message) return '';

  // Try to extract a user-friendly message from error_message
  let userMsg = run.error_message;
  try {
    // If it looks like JSON, try to parse it
    if (userMsg.startsWith('{')) {
      const parsed = JSON.parse(userMsg);
      userMsg = parsed.user_message || parsed.message || parsed.detail || userMsg;
    }
  } catch {}

  // Truncate very long messages
  if (userMsg.length > 300) {
    userMsg = userMsg.substring(0, 300) + '…';
  }

  // Build action buttons
  let actions = '';
  if (run.current_stage) {
    actions = `<button class="error-banner-action" onclick="resumePipeline('${run.run_id}')">↻ Resume from ${escHtml(run.current_stage.replace(/_/g, ' '))}</button>`;
    actions += `<button class="error-banner-action" style="background:var(--bg-tertiary);color:var(--text-primary);margin-left:6px" onclick="deleteRun('${run.run_id}')">🗑 Delete</button>`;
  }

  return `
    <div class="error-banner">
      <div class="error-banner-header">
        <span>⚠</span>
        <span>Pipeline Error</span>
      </div>
      <div class="error-banner-message">${escHtml(userMsg)}</div>
      ${actions}
    </div>`;
}

function showRunDetail(run, iterations = []) {
  const stages = run.stages || {};
  const isWaiting = run.status === 'waiting_human';

  // Error banner for failed runs
  const errorBannerHtml = _buildErrorBanner(run);

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
            <div class="topic-card" onclick="approveTopicSelection('${run.run_id}', ${i}, ${JSON.stringify(idea).replace(/"/g, '&quot;')})">
              <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
                <span style="background:var(--accent-info);color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">${escHtml(idea.gap_type || '')}</span>
                ${idea.urgency ? '<span style="font-size:11px;color:var(--accent-warning)">🔥 Urgent</span>' : ''}
              </div>
              <div style="font-size:15px;font-weight:600;margin-bottom:6px">${escHtml(idea.title || 'Untitled')}</div>
              <div style="font-size:13px;color:var(--text-secondary);margin-bottom:8px">❓ ${escHtml(idea.subtitle || '')}</div>
              <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px">
                <em>"${escHtml(idea.mainstream_assumption || '')}"</em>
              </div>
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                <div style="flex:1;height:6px;background:var(--border);border-radius:3px;overflow:hidden">
                  <div style="height:100%;background:var(--accent-primary);width:${((idea.viability_total || 0) / 17) * 100}%"></div>
                </div>
                <span style="font-size:12px;font-weight:600">${idea.viability_total || 0}/17</span>
              </div>
              <div style="display:flex;gap:10px;font-size:12px;margin-bottom:8px">
                <span style="color:${idea.gap_pass ? 'var(--accent-success)' : 'var(--accent-error)'}">${idea.gap_pass ? '✓' : '✗'} Gap</span>
                <span style="color:${(idea.anchor_pass || 0) >= 2 ? 'var(--accent-success)' : 'var(--accent-error)'}">${idea.anchor_pass || 0}/4 Anchors</span>
                <span style="color:${(idea.audience_pass || 0) >= 2 ? 'var(--accent-success)' : 'var(--accent-error)'}">${idea.audience_pass || 0}/4 Audience</span>
              </div>
              <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px">
                ${(idea.anchors || []).map(a => `<span style="background:var(--bg-hover);border:1px solid var(--border);padding:2px 8px;border-radius:10px;font-size:11px">${escHtml(a)}</span>`).join('')}
              </div>
              <div style="font-size:11px;color:var(--text-muted);margin-bottom:12px">⏱ ${escHtml(idea.timing || '')}</div>
              <button class="btn btn-primary" style="width:100%">Pick This Topic →</button>
            </div>`).join('') ||
        `<p style="color:var(--text-muted)">No candidates found</p>`}
          </div>
        </div>`;
    } else if (run.current_stage === 'human_review') {
      // Extract script content from the script_writing stage output
      const scriptOutput = stages.script_writing?.output || {};
      const scriptTitle = scriptOutput.adapted_title || run.video_title || 'Untitled';
      const scriptScore = scriptOutput.production_readiness_score;
      const entries = Array.isArray(scriptOutput.entries) ? scriptOutput.entries : [];

      // Build a readable script view from dual-column entries
      let scriptContentHtml = '';
      if (entries.length > 0) {
        scriptContentHtml = entries.map((entry, idx) => {
          const prose = entry.prose || '';
          const visual = entry.visual_direction || '';
          const section = entry.section_label || '';
          const isAnchor = section === 'ANCHOR';
          const isHook = section === 'HOOK';
          const headerStyle = isAnchor ? 'color:var(--accent-warning);font-weight:700' :
                              isHook ? 'color:var(--accent-primary);font-weight:700' :
                              'color:var(--text-muted);font-weight:600';
          return `
            <div style="margin-bottom:12px;padding:8px 0;${isAnchor || isHook ? 'border-left:3px solid ' + (isAnchor ? 'var(--accent-warning)' : 'var(--accent-primary)') + ';padding-left:12px' : ''}">
              ${section ? `<div style="font-size:11px;text-transform:uppercase;${headerStyle};margin-bottom:4px">${escHtml(section)}</div>` : ''}
              <div style="font-size:13px;line-height:1.6;color:var(--text-primary)">${escHtml(prose)}</div>
              ${visual ? `<div style="font-size:11px;color:var(--text-muted);margin-top:4px;font-style:italic">📹 ${escHtml(visual)}</div>` : ''}
            </div>`;
        }).join('');
      } else {
        // Fallback: show raw JSON if no structured entries
        scriptContentHtml = `<pre style="font-size:12px;color:var(--text-secondary);max-height:400px;overflow-y:auto">${escHtml(JSON.stringify(scriptOutput, null, 2))}</pre>`;
      }

      approvalHtml = `
        <div class="card" style="border-color:var(--accent-warning);margin-bottom:12px">
          <div class="card-header">
            <h3 style="color:var(--accent-warning)">👁️ Review script & visual plan</h3>
            ${scriptScore ? `<span style="font-size:13px;font-weight:700;color:${scriptScore >= 85 ? 'var(--accent-success)' : 'var(--accent-warning)'}">${scriptScore.toFixed(1)}%</span>` : ''}
          </div>
          <div style="margin-bottom:12px">
            <div style="font-size:15px;font-weight:700;margin-bottom:8px">${escHtml(scriptTitle)}</div>
            <div style="max-height:500px;overflow-y:auto;padding:12px;background:var(--bg-tertiary);border-radius:var(--radius)">
              ${scriptContentHtml}
            </div>
          </div>
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

  // Stage outputs (expandable) - render as readable HTML
  const outputsHtml = STAGE_ORDER
    .filter(s => stages[s]?.output)
    .map(s => `
      <div style="margin-bottom:8px;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden">
        <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;cursor:pointer;background:var(--bg-tertiary)"
             onclick="this.nextElementSibling.classList.toggle('open')">
          <span>${STAGE_ICONS[s]} ${STAGE_LABELS[s]}</span>
          <span style="color:var(--text-muted);font-size:12px">▾</span>
        </div>
        <div class="expandable" style="padding:0;max-height:400px;overflow-y:auto">
          ${renderArtifactHtml(stages[s].output, s)}
        </div>
      </div>`).join('');

  // Iteration graph
  let graphHtml = '';
  if (iterations && iterations.length > 0) {
    const maxScore = Math.max(...iterations.map(it => it.score), 100);
    const bars = iterations.map(it => {
      const height = Math.max(5, (it.score / maxScore) * 100);
      const color = it.beat_baseline ? 'var(--accent-success)' : 'var(--accent-secondary)';
      // Store iteration data as JSON attribute for click handler
      const iterData = JSON.stringify(it).replace(/"/g, '&quot;');
      return `<div title="Iteration ${it.iteration}: ${it.score.toFixed(1)}% (${it.mutation_zone}) - Click to view script"
                   data-iteration='${iterData}'
                   onclick="showIterationScript(this)"
                   style="flex:1;height:${height}%;background:${color};border-radius:2px 2px 0 0;cursor:pointer"></div>`;
    }).join('');

    graphHtml = `
      <div class="card" style="margin-bottom:16px;background:var(--bg-secondary)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <span style="font-size:13px;font-weight:600">📈 Script Evolution (${iterations.length} iters)</span>
          <span style="font-size:12px;font-weight:700;color:var(--accent-success)">${iterations[iterations.length - 1].score.toFixed(1)}%</span>
        </div>
        <div style="display:flex;align-items:flex-end;gap:2px;height:60px;background:rgba(0,0,0,0.2);padding:4px;border-radius:4px;margin-bottom:8px">
          ${bars}
        </div>
        <div style="font-size:11px;color:var(--text-muted);display:flex;justify-content:space-between">
          <span>Baseline: ${iterations[0].previous_score.toFixed(1)}%</span>
          <span>Target: 85%</span>
        </div>
      </div>`;
  } else {
    graphHtml = `<div style="padding:12px;text-align:center;color:var(--text-muted);font-size:12px;border:1px dashed var(--border);border-radius:var(--radius);margin-bottom:16px">
      Waiting for script evolution to start...
    </div>`;
  }

  // Feedback loop
  const isScriptActive = ['running', 'complete'].includes(stages.script_writing?.status);
  const feedbackHtml = isScriptActive ? `
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
      <h2 style="font-size:16px;color:var(--text-primary)">${escHtml(run.video_title || 'Pipeline Run')}</h2>
      <div style="display:flex;gap:8px">
        <button class="btn btn-danger btn-sm" onclick="deleteRun('${run.run_id}')">Delete</button>
        <button class="btn btn-outline btn-sm" onclick="hideModal()">✕</button>
      </div>
    </div>
    <div class="pipeline-graph" style="margin-bottom:16px">${renderMiniGraph(run.stages)}</div>
    ${errorBannerHtml}
    ${approvalHtml}
    ${outputsHtml}
    ${graphHtml}
    ${feedbackHtml}
  `);
}

async function startNewPipeline() {
  showModal(`
    <h3 style="color:var(--text-primary);margin-bottom:16px">Start new pipeline</h3>
    <div class="form-group">
      <label class="form-label">Topic (optional — leave blank for trend analysis)</label>
      <input type="text" id="new-topic" class="form-input"
             placeholder="e.g. Why Pakistan's AI policy matters"
             maxlength="200">
      <div id="topic-validation-error" class="inline-error" style="display:none"></div>
    </div>
    <div style="display:flex;gap:8px;justify-content:flex-end">
      <button class="btn btn-outline" onclick="hideModal()">Cancel</button>
      <button class="btn btn-primary" onclick="confirmStart()">Start</button>
    </div>`);

  // Attach blur validation (validate on blur, not on every keystroke)
  const topicInput = document.getElementById('new-topic');
  if (topicInput) {
    topicInput.addEventListener('blur', () => _validateTopicInput());
  }
}

function _validateTopicInput() {
  const input = document.getElementById('new-topic');
  const errorEl = document.getElementById('topic-validation-error');
  if (!input || !errorEl) return true;

  const val = input.value.trim();

  // If empty, it's valid (topic is optional)
  if (!val) {
    input.classList.remove('error', 'valid');
    errorEl.style.display = 'none';
    return true;
  }

  // Validate min/max length
  if (val.length < 5) {
    input.classList.add('error');
    input.classList.remove('valid');
    errorEl.textContent = 'Topic must be at least 5 characters';
    errorEl.style.display = 'block';
    return false;
  }

  if (val.length > 200) {
    input.classList.add('error');
    input.classList.remove('valid');
    errorEl.textContent = 'Topic must be less than 200 characters';
    errorEl.style.display = 'block';
    return false;
  }

  input.classList.remove('error');
  input.classList.add('valid');
  errorEl.style.display = 'none';
  return true;
}

async function confirmStart() {
  // Run client-side validation before submitting
  if (!_validateTopicInput()) {
    // Focus the input to draw attention to the error
    const input = document.getElementById('new-topic');
    if (input) input.focus();
    return;
  }

  const topic = document.getElementById('new-topic').value.trim();
  hideModal();
  try {
    const r = await api('/api/pipeline/runs', { method: 'POST', body: { topic } });
    showToast(`Pipeline started: ${r.run_id.slice(0, 8)}`, 'success');
    await refreshPipeline();
  } catch (e) {
    showToast(`Failed: ${e.message}`, 'error');
  }
}

async function resumePipeline(runId) {
  try {
    const r = await api(`/api/pipeline/runs/${runId}/resume`, { method: 'POST' });
    hideModal();
    showToast(`Pipeline resumed from stage: ${r.current_stage || 'previous'}`, 'success');
    await refreshPipeline();
  } catch (e) {
    showToast(`Resume failed: ${e.message}`, 'error');
  }
}

async function approveTopicSelection(runId, i, idea) {
  try {
    await api(`/api/pipeline/runs/${runId}/approve`, { method: 'POST', body: { selection: idea } });
    hideModal();
    showToast('Topic selected — research starting…', 'success');
    const badge = document.getElementById('pipeline-badge');
    const n = Math.max(0, parseInt(badge.textContent || '1') - 1);
    badge.textContent = n;
    if (n === 0) badge.classList.add('hidden');
    await refreshPipeline();
  } catch (e) { showToast(`Approval failed: ${e.message}`, 'error'); }
}

async function approveReview(runId) {
  const feedback = document.getElementById('review-feedback')?.value || '';
  try {
    await api(`/api/pipeline/runs/${runId}/approve`, { method: 'POST', body: { feedback } });
    hideModal();
    showToast('Approved — assets generating…', 'success');
    await refreshPipeline();
  } catch (e) { showToast(`Approval failed: ${e.message}`, 'error'); }
}

async function rejectReview(runId) {
  const feedback = document.getElementById('review-feedback')?.value || '';
  if (!feedback) { showToast('Please add feedback before rejecting', 'warning'); return; }
  try {
    await api(`/api/pipeline/runs/${runId}/reject`, { method: 'POST', body: { feedback } });
    hideModal();
    showToast('Sent back for revision', 'info');
    await refreshPipeline();
  } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}

async function sendFeedback(runId) {
  const feedback = document.getElementById('feedback-text')?.value || '';
  if (!feedback) { showToast('Please add feedback', 'warning'); return; }
  try {
    await api(`/api/pipeline/runs/${runId}/feedback`, {
      method: 'POST', body: { from_stage: 'script_writing', to_stage: 'research', feedback }
    });
    hideModal();
    showToast('Feedback sent to researcher', 'info');
  } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}

async function deleteRun(runId) {
  if (!confirm('Delete this pipeline run?')) return;
  try {
    await api(`/api/pipeline/runs/${runId}`, { method: 'DELETE' });
    hideModal();
    showToast('Run deleted', 'info');
    await refreshPipeline();
  } catch (e) { showToast(`Delete failed: ${e.message}`, 'error'); }
}

/**
 * Show the script for a specific iteration when clicking on a graph bar.
 * @param {HTMLElement} barEl - The clicked bar element with data-iteration attribute
 */
function showIterationScript(barEl) {
  const iterData = barEl.dataset.iteration;
  if (!iterData) return;
  
  try {
    const iter = JSON.parse(iterData);
    const scriptJson = iter.script_json;
    
    if (!scriptJson) {
      showToast('No script data for this iteration', 'warning');
      return;
    }
    
    // Build readable script display
    let content = '';
    
    // Show iteration header
    content += `<div style="margin-bottom:12px;padding:10px;background:var(--bg-tertiary);border-radius:var(--radius)">`;
    content += `<div style="display:flex;justify-content:space-between;align-items:center">`;
    content += `<span style="font-weight:600">Iteration ${iter.iteration}</span>`;
    content += `<span style="font-weight:700;color:var(--accent-success)">${iter.score.toFixed(1)}%</span>`;
    content += `</div>`;
    content += `<div style="font-size:12px;color:var(--text-muted);margin-top:4px">`;
    content += `Mutation: ${escHtml(iter.mutation_zone || 'N/A')} | `;
    content += iter.beat_baseline ? '<span style="color:var(--accent-success)">✓ Beat baseline</span>' : '<span style="color:var(--text-muted)">Did not beat baseline</span>';
    content += `</div>`;
    content += `</div>`;
    
    // Show script content
    if (scriptJson.entries && Array.isArray(scriptJson.entries)) {
      // Dual-column script format (AdaptedScript)
      content += `<div style="font-size:12px">`;
      content += `<table style="width:100%;border-collapse:collapse">`;
      content += `<thead><tr style="background:var(--bg-tertiary)">`;
      content += `<th style="padding:8px;text-align:left;border-bottom:1px solid var(--border)">Narration</th>`;
      content += `<th style="padding:8px;text-align:left;border-bottom:1px solid var(--border)">Visual</th>`;
      content += `</tr></thead>`;
      content += `<tbody>`;
      scriptJson.entries.forEach((entry, i) => {
        const bgStyle = i % 2 === 0 ? '' : 'background:var(--bg-secondary)';
        content += `<tr style="${bgStyle}">`;
        content += `<td style="padding:8px;vertical-align:top;border-bottom:1px solid var(--border)">${escHtml(entry.prose || '')}</td>`;
        content += `<td style="padding:8px;vertical-align:top;border-bottom:1px solid var(--border);color:var(--text-secondary)">${escHtml(entry.visual_direction || '')}</td>`;
        content += `</tr>`;
      });
      content += `</tbody></table>`;
      content += `</div>`;
      
      // Show title if available
      if (scriptJson.adapted_title) {
        content = `<div style="margin-bottom:12px;font-weight:600;font-size:14px">${escHtml(scriptJson.adapted_title)}</div>` + content;
      }
    } else {
      // Fallback: show raw JSON
      content += `<pre style="margin:0;max-height:400px;overflow:auto">${escHtml(JSON.stringify(scriptJson, null, 2))}</pre>`;
    }
    
    // Show failed questions if any
    if (iter.failed_questions && iter.failed_questions.length > 0) {
      content += `<div style="margin-top:12px;padding:8px;background:rgba(161,42,42,0.2);border-radius:var(--radius)">`;
      content += `<div style="font-size:11px;font-weight:600;color:var(--accent-error)">Failed questions: ${iter.failed_questions.join(', ')}</div>`;
      content += `</div>`;
    }
    
    showModal(`
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h2 style="font-size:15px;color:var(--text-primary)">📄 Script at Iteration ${iter.iteration}</h2>
        <button class="btn btn-outline btn-sm" onclick="hideModal()">✕</button>
      </div>
      ${content}
    `);
    
  } catch (e) {
    console.error('Failed to parse iteration data:', e);
    showToast('Failed to display iteration script', 'error');
  }
}
