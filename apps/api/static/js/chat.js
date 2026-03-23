/**
 * chat.js — Chat tab with persistent conversation history.
 *
 * Ports all functionality from freerouter/web/static/js/chat.js to the
 * new dark-theme dashboard. Talks to /api/chat/* which proxies to
 * FreeRouter at :8080. Streaming, conversation history, provider badge
 * all work identically — just restyled.
 */

const _chatState = {
  convId: null,
  messages: [],
  streaming: false,
};

async function initChat() {
  const el = document.getElementById('tab-chat');
  el.innerHTML = `
    <div class="chat-layout">
      <div class="chat-sidebar">
        <div class="chat-sidebar-header">
          <span class="chat-sidebar-title">History</span>
          <button class="btn btn-sm btn-outline" onclick="newConversation()">+ New</button>
        </div>
        <div id="conv-list" class="conv-list">
          <div class="conv-empty">Loading…</div>
        </div>
      </div>
      <div class="chat-main">
        <div class="chat-toolbar">
          <label>Model</label>
          <select id="chat-model" class="model-select">
            <option value="auto">⚡ Auto (best available)</option>
          </select>
          <button class="btn btn-sm btn-outline" onclick="clearChat()">Clear</button>
        </div>
        <div id="chat-messages" class="chat-messages">
          <div class="chat-welcome">
            <strong>FreeRouter Chat</strong>
            <p>Routes to the best free provider automatically.<br>
            Provider badge shown on each response.<br>
            History persists across restarts.</p>
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

  // Load models
  try {
    const data = await api('/api/chat/models');
    const sel = document.getElementById('chat-model');
    if (data.models?.length) {
      sel.innerHTML = data.models.map(m =>
        `<option value="${escHtml(m.id)}">${escHtml(m.display||m.id)}</option>`).join('');
    }
  } catch {}

  await loadConvList();

  document.getElementById('chat-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
  });
}

// ─── Conversation list ────────────────────────────────────────────────────────

async function loadConvList() {
  try {
    const data = await api('/api/chat/conversations');
    const list = document.getElementById('conv-list');
    const convs = data.conversations || [];
    if (!convs.length) {
      list.innerHTML = '<div class="conv-empty">No conversations yet</div>';
      return;
    }
    list.innerHTML = convs.map(c => `
      <div class="conv-item ${c.id === _chatState.convId ? 'active' : ''}"
           onclick="loadConv('${c.id}')">
        <div class="conv-title">${escHtml(c.title||'Untitled')}</div>
        <div class="conv-meta">${c.message_count||0} messages</div>
        <button class="conv-del" onclick="delConv(event,'${c.id}')">×</button>
      </div>`).join('');
  } catch (e) {
    document.getElementById('conv-list').innerHTML =
      `<div class="conv-empty" style="color:var(--accent-warning)">FreeRouter offline</div>`;
  }
}

async function newConversation() {
  const data = await api('/api/chat/conversations', {method:'POST', body:{}});
  _chatState.convId = data.id;
  _chatState.messages = [];
  document.getElementById('chat-messages').innerHTML =
    `<div class="chat-welcome"><strong>New conversation</strong><p>Start typing below.</p></div>`;
  await loadConvList();
}

async function loadConv(cid) {
  try {
    const conv = await api(`/api/chat/conversations/${cid}`);
    _chatState.convId = cid;
    _chatState.messages = conv.messages || [];
    const container = document.getElementById('chat-messages');
    if (!conv.messages.length) {
      container.innerHTML = `<div class="chat-welcome"><strong>${escHtml(conv.title||'Chat')}</strong><p>No messages yet.</p></div>`;
    } else {
      container.innerHTML = conv.messages.map(m => renderMsg(m)).join('');
      container.scrollTop = container.scrollHeight;
    }
    await loadConvList();
  } catch (e) { showToast('Could not load: '+e.message, 'error'); }
}

async function delConv(e, cid) {
  e.stopPropagation();
  if (!confirm('Delete this conversation?')) return;
  await api(`/api/chat/conversations/${cid}`, {method:'DELETE'}).catch(()=>{});
  if (_chatState.convId === cid) {
    _chatState.convId = null;
    _chatState.messages = [];
    document.getElementById('chat-messages').innerHTML =
      `<div class="chat-welcome"><strong>Deleted</strong><p>Start a new conversation.</p></div>`;
  }
  await loadConvList();
}

function clearChat() {
  _chatState.convId = null;
  _chatState.messages = [];
  document.getElementById('chat-messages').innerHTML =
    `<div class="chat-welcome"><strong>Cleared</strong><p>Start typing to begin.</p></div>`;
}

// ─── Send ─────────────────────────────────────────────────────────────────────

async function sendChatMessage() {
  if (_chatState.streaming) return;
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  if (!_chatState.convId) {
    const data = await api('/api/chat/conversations', {method:'POST', body:{}});
    _chatState.convId = data.id;
  }

  input.value = '';
  _chatState.streaming = true;
  document.getElementById('chat-send').disabled = true;

  const userMsg = {role:'user', content:text, timestamp:new Date().toISOString()};
  _chatState.messages.push(userMsg);
  appendMsg(userMsg);

  try {
    await api(`/api/chat/conversations/${_chatState.convId}/messages`,
              {method:'POST', body:{role:'user', content:text}});
  } catch {}

  const aid = 'cm-' + Date.now();
  appendStreamingPlaceholder(aid);

  try {
    const model = document.getElementById('chat-model')?.value || 'auto';
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        model,
        messages: _chatState.messages.map(m => ({role:m.role, content:m.content})),
        temperature: 0.7,
        max_tokens: 4096,
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(()=>({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    const {content, provider, model: usedModel} = await readChatStream(resp, aid);
    const assistantMsg = {
      role:'assistant', content:content||'(no response)',
      timestamp:new Date().toISOString(), provider, model:usedModel,
    };
    _chatState.messages.push(assistantMsg);
    finalizeMsg(aid, assistantMsg);

    try {
      await api(`/api/chat/conversations/${_chatState.convId}/messages`, {
        method:'POST',
        body:{role:'assistant', content:assistantMsg.content, provider, model:usedModel},
      });
      await loadConvList();
    } catch {}

  } catch (e) {
    setMsgError(aid, e.message);
    showToast('Error: '+e.message, 'error');
  } finally {
    _chatState.streaming = false;
    document.getElementById('chat-send').disabled = false;
    document.getElementById('chat-input')?.focus();
  }
}

// ─── Stream reader ────────────────────────────────────────────────────────────

async function readChatStream(resp, id) {
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let full='', buf='', provider='', usedModel='';

  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buf += dec.decode(value, {stream:true});
    const lines = buf.split('\n');
    buf = lines.pop() || '';

    for (const line of lines) {
      const t = line.trim();
      if (!t.startsWith('data: ')) continue;
      const d = t.slice(6);
      if (d === '[DONE]' || !d) continue;
      try {
        const p = JSON.parse(d);
        if (p.error) throw new Error(typeof p.error==='string' ? p.error : p.error.message||'Error');
        if (p.meta?._provider) {
          provider = p.meta._provider;
          usedModel = p.meta._model||'';
          updateStreamProvider(id, provider, usedModel);
          continue;
        }
        const delta = p.choices?.[0]?.delta?.content;
        if (delta) { full += delta; updateStreamContent(id, full); }
      } catch(e) {
        if (!e.message.includes('JSON')) throw e;
      }
    }
  }
  return {content:full, provider, model:usedModel};
}

// ─── DOM helpers ──────────────────────────────────────────────────────────────

function renderMsg(msg) {
  const tag = (msg.role==='assistant' && msg.provider)
    ? `<span class="provider-tag">${escHtml(msg.provider)}${msg.model?' / '+escHtml(msg.model):''}</span>`
    : '';
  return `
    <div class="chat-msg ${msg.role}">
      <div class="msg-header">
        ${msg.role==='user'?'You':'Assistant'} ${tag}
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
        <span class="provider-tag" id="${id}-p">routing…</span>
      </div>
      <div class="msg-body"><span class="thinking-dots"></span></div>
    </div>`);
  c.scrollTop = c.scrollHeight;
}

function updateStreamProvider(id, provider, model) {
  const el = document.getElementById(`${id}-p`);
  if (el) el.textContent = `${provider}${model?' / '+model:''}`;
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
  const tag = msg.provider
    ? `<span class="provider-tag">${escHtml(msg.provider)}${msg.model?' / '+escHtml(msg.model):''}</span>`
    : '';
  el.querySelector('.msg-header').innerHTML =
    `Assistant ${tag} <span style="font-size:10px;color:var(--text-muted)">${fmtTime(msg.timestamp)}</span>`;
  el.querySelector('.msg-body').textContent = msg.content;
}

function setMsgError(id, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.querySelector('.msg-header').innerHTML =
    'Assistant <span class="provider-tag error-tag">failed</span>';
  el.querySelector('.msg-body').innerHTML =
    `<span style="color:var(--accent-error)">Error: ${escHtml(text)}</span>`;
}
