/**
 * chat.js — Chat tab with LangGraph ReAct agent.
 *
 * Talks to /api/chat/* which uses a LangGraph agent with tool calling.
 * Supports streaming responses, session-based conversations via
 * LangGraph checkpointer, and tool call visibility in the UI.
 *
 * Conversation metadata (session list) is persisted in localStorage
 * since the backend does not provide conversation CRUD endpoints.
 * Actual message history is fetched from GET /api/chat/history/{session_id}.
 */

const _chatState = {
  sessionId: null,
  messages: [],
  streaming: false,
};

// ─── Session persistence (localStorage) ────────────────────────────────────────

function _getSessions() {
  try { return JSON.parse(localStorage.getItem('chat_sessions') || '[]'); }
  catch { return []; }
}

function _saveSessions(sessions) {
  localStorage.setItem('chat_sessions', JSON.stringify(sessions));
}

function _addSession(sessionId, title) {
  const sessions = _getSessions();
  const filtered = sessions.filter(s => s.id !== sessionId);
  filtered.unshift({
    id: sessionId,
    title: (title || 'New Chat').slice(0, 80),
    created_at: new Date().toISOString(),
  });
  // Keep only the last 30 sessions
  if (filtered.length > 30) filtered.length = 30;
  _saveSessions(filtered);
}

function _removeSession(sessionId) {
  const sessions = _getSessions().filter(s => s.id !== sessionId);
  _saveSessions(sessions);
}

// ─── Init ───────────────────────────────────────────────────────────────────────

async function initChat() {
  const el = document.getElementById('tab-chat');
  el.innerHTML = `
    <div class="chat-layout">
      <div class="chat-sidebar">
        <div class="chat-sidebar-header">
          <span class="chat-sidebar-title">History</span>
          <button class="btn btn-sm btn-outline" onclick="newChatSession()">+ New</button>
        </div>
        <div id="conv-list" class="conv-list"></div>
      </div>
      <div class="chat-main">
        <div class="chat-toolbar">
          <button class="btn btn-sm btn-outline" onclick="clearChat()">Clear</button>
        </div>
        <div id="chat-messages" class="chat-messages">
          <div class="chat-welcome">
            <strong>AI Chat</strong>
            <p>Powered by LangGraph ReAct agent.<br>
            Tool calls are shown during processing.<br>
            Conversation history persists per session.</p>
          </div>
        </div>
        <div class="chat-input-row">
          <textarea id="chat-input" class="chat-input"
            placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
            rows="3"></textarea>
          <button id="chat-send" class="btn btn-primary" onclick="sendChatMessage()">Send</button>
        </div>
      </div>
    </div>`;

  await loadConvList();

  document.getElementById('chat-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
  });
}

// ─── Conversation list (localStorage-backed) ────────────────────────────────────

function loadConvList() {
  const sessions = _getSessions();
  const list = document.getElementById('conv-list');
  if (!sessions.length) {
    list.innerHTML = '<div class="conv-empty">No conversations yet</div>';
    return;
  }
  list.innerHTML = sessions.map(s => `
    <div class="conv-item ${s.id === _chatState.sessionId ? 'active' : ''}"
         onclick="loadSession('${s.id}')">
      <div class="conv-title">${escHtml(s.title || 'Untitled')}</div>
      <div class="conv-meta">${fmtDate(s.created_at)}</div>
      <button class="conv-del" onclick="delSession(event,'${s.id}')">×</button>
    </div>`).join('');
}

// Kept as async for compatibility with old callers, but does not call any API.
async function newConversation() { newChatSession(); }

function newChatSession() {
  _chatState.sessionId = null;
  _chatState.messages = [];
  document.getElementById('chat-messages').innerHTML =
    `<div class="chat-welcome"><strong>New conversation</strong><p>Start typing below.</p></div>`;
  loadConvList();
}

async function loadConv(cid) { loadSession(cid); }

async function loadSession(sid) {
  _chatState.sessionId = sid;
  _chatState.messages = [];
  const container = document.getElementById('chat-messages');
  container.innerHTML = `<div class="chat-welcome"><strong>Loading…</strong></div>`;

  try {
    // Fetch actual message history from LangGraph checkpointer
    const data = await api(`/api/chat/history/${sid}`);
    _chatState.messages = data.messages || [];

    const session = _getSessions().find(s => s.id === sid);
    if (!_chatState.messages.length) {
      container.innerHTML =
        `<div class="chat-welcome"><strong>${escHtml(session?.title || 'Chat')}</strong><p>No messages yet.</p></div>`;
    } else {
      container.innerHTML = _chatState.messages.map(m => renderMsg(m)).join('');
      container.scrollTop = container.scrollHeight;
    }
  } catch (e) {
    container.innerHTML =
      `<div class="chat-welcome"><strong>Error</strong><p>Could not load: ${escHtml(e.message)}</p></div>`;
  }
  loadConvList();
}

function delConv(e, cid) { delSession(e, cid); }

async function delSession(e, sid) {
  e.stopPropagation();
  if (!confirm('Delete this conversation from local history?')) return;
  _removeSession(sid);
  if (_chatState.sessionId === sid) {
    newChatSession();
  } else {
    loadConvList();
  }
}

function clearChat() {
  _chatState.sessionId = null;
  _chatState.messages = [];
  document.getElementById('chat-messages').innerHTML =
    `<div class="chat-welcome"><strong>Cleared</strong><p>Start typing to begin.</p></div>`;
  loadConvList();
}

// ─── Send ───────────────────────────────────────────────────────────────────────

async function sendChatMessage() {
  if (_chatState.streaming) return;
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  _chatState.streaming = true;
  document.getElementById('chat-send').disabled = true;

  const userMsg = { role: 'user', content: text, timestamp: new Date().toISOString() };
  _chatState.messages.push(userMsg);
  appendMsg(userMsg);

  const aid = 'cm-' + Date.now();
  appendStreamingPlaceholder(aid);

  try {
    // Backend expects ChatRequest: { message: str, session_id: str | None }
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: _chatState.sessionId || undefined,
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    // Parse LangGraph SSE stream: {type: "token/tool_start/tool_end/done/error"}
    const { content, sessionId, toolsUsed } = await readChatStream(resp, aid);

    // Update session ID from backend response for conversation continuity
    if (sessionId) {
      _chatState.sessionId = sessionId;
    }

    const assistantMsg = {
      role: 'assistant',
      content: content || '(no response)',
      timestamp: new Date().toISOString(),
      tools_used: toolsUsed,
    };
    _chatState.messages.push(assistantMsg);
    finalizeMsg(aid, assistantMsg);

    // Save session to localStorage for sidebar persistence
    if (_chatState.sessionId) {
      _addSession(_chatState.sessionId, text);
    }
    loadConvList();

  } catch (e) {
    setMsgError(aid, e.message);
    showToast('Error: ' + e.message, 'error');
  } finally {
    _chatState.streaming = false;
    document.getElementById('chat-send').disabled = false;
    document.getElementById('chat-input')?.focus();
  }
}

// ─── Stream reader (LangGraph ReAct SSE format) ────────────────────────────────

async function readChatStream(resp, id) {
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let full = '';
  let buf = '';
  let sessionId = null;
  const toolsUsed = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() || '';

    for (const line of lines) {
      const t = line.trim();
      if (!t.startsWith('data: ')) continue;
      const d = t.slice(6);
      if (!d) continue;

      try {
        const p = JSON.parse(d);
        const type = p.type;

        if (type === 'error') {
          throw new Error(typeof p.message === 'string' ? p.message : 'Stream error');
        }

        if (type === 'tool_start') {
          toolsUsed.push(p.tool);
          showToolIndicator(id, p.tool, 'started');
          continue;
        }

        if (type === 'tool_end') {
          showToolIndicator(id, p.tool, 'completed');
          continue;
        }

        if (type === 'done') {
          if (p.session_id) sessionId = p.session_id;
          continue;
        }

        if (type === 'token' && p.content) {
          full += p.content;
          updateStreamContent(id, full);
        }
      } catch (e) {
        // Only re-throw non-JSON errors (real errors, not parse failures)
        if (e.message && !e.message.includes('JSON')) throw e;
      }
    }
  }
  return { content: full, sessionId, toolsUsed: [...new Set(toolsUsed)] };
}

// ─── DOM helpers ───────────────────────────────────────────────────────────────

function renderMsg(msg) {
  const tag = (msg.role === 'assistant' && msg.tools_used?.length)
    ? `<span class="provider-tag">🔧 ${escHtml(msg.tools_used.join(', '))}</span>`
    : '';
  return `
    <div class="chat-msg ${msg.role}">
      <div class="msg-header">
        ${msg.role === 'user' ? 'You' : 'Assistant'} ${tag}
        <span style="font-size:10px;color:var(--text-muted)">${fmtTime(msg.timestamp)}</span>
      </div>
      <div class="msg-body">${escHtml(msg.content)}</div>
    </div>`;
}

function appendMsg(msg) {
  const c = document.getElementById('chat-messages');
  c.querySelector('.chat-welcome')?.remove();
  c.insertAdjacentHTML('beforeend', renderMsg(msg));
  c.scrollTop = c.scrollHeight;
}

function appendStreamingPlaceholder(id) {
  const c = document.getElementById('chat-messages');
  c.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="chat-msg assistant">
      <div class="msg-header">Assistant
        <span class="provider-tag" id="${id}-p">thinking…</span>
      </div>
      <div class="msg-body"><span class="thinking-dots"></span></div>
      <div class="msg-tools" id="${id}-tools"></div>
    </div>`);
  c.scrollTop = c.scrollHeight;
}

/** Show tool call indicators during streaming. */
function showToolIndicator(id, toolName, state) {
  const toolsEl = document.getElementById(`${id}-tools`);
  const statusEl = document.getElementById(`${id}-p`);
  if (!toolsEl) return;

  // Update header status
  if (statusEl) {
    statusEl.textContent = state === 'started'
      ? `🔧 Using ${toolName}…`
      : `🔧 ${toolName} done`;
  }

  // Show tool pill in tools area
  const pillId = `tool-${id}-${toolName}`;
  let pill = document.getElementById(pillId);
  if (!pill) {
    pill = document.createElement('span');
    pill.id = pillId;
    pill.className = 'tool-pill';
    pill.style.cssText = 'display:inline-block;font-size:10px;padding:2px 6px;margin:2px;border-radius:4px;';
    pill.textContent = toolName;
    toolsEl.appendChild(pill);
  }
  pill.style.background = state === 'started' ? 'var(--bg-tertiary)' : 'var(--accent-success, #2da44e)';
  pill.style.color = state === 'started' ? 'var(--text-primary)' : '#fff';
  pill.textContent = state === 'started' ? `⏳ ${toolName}` : `✓ ${toolName}`;
}

function updateStreamContent(id, content) {
  const el = document.getElementById(id);
  if (!el) return;
  el.querySelector('.msg-body').textContent = content;
  document.getElementById('chat-messages').scrollTop = 99999;
}

function finalizeMsg(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;

  const tag = msg.tools_used?.length
    ? `<span class="provider-tag">🔧 ${escHtml(msg.tools_used.join(', '))}</span>`
    : '';

  el.querySelector('.msg-header').innerHTML =
    `Assistant ${tag} <span style="font-size:10px;color:var(--text-muted)">${fmtTime(msg.timestamp)}</span>`;
  el.querySelector('.msg-body').textContent = msg.content;

  // Clean up tools indicator area
  const toolsEl = document.getElementById(`${id}-tools`);
  if (toolsEl) toolsEl.remove();
}

function setMsgError(id, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.querySelector('.msg-header').innerHTML =
    'Assistant <span class="provider-tag error-tag">failed</span>';
  el.querySelector('.msg-body').innerHTML =
    `<span style="color:var(--accent-error)">Error: ${escHtml(text)}</span>`;
  // Clean up tools indicator area
  const toolsEl = document.getElementById(`${id}-tools`);
  if (toolsEl) toolsEl.remove();
}
