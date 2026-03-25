/**
 * chat.js — Chat tab with persistent conversation history.
 *
 * Context: Conversations are saved to SQLite via /api/conversations.
 * History survives server restarts. Shows sidebar of past conversations.
 * Each message shows which provider/model handled it.
 *
 * Storage flow:
 *   1. User sends message → saved to DB via POST /api/conversations/{id}/messages
 *   2. Assistant responds → saved to DB with provider+model info
 *   3. On reload → GET /api/conversations loads history from DB
 *
 * Depends on: ui.js (apiFetch, showToast, escapeHtml, formatTime)
 */

const chatState = {
  model: 'auto',
  conversationId: null,
  messages: [],       // in-memory mirror of current conversation
  isStreaming: false,
};

// ─── Init ─────────────────────────────────────────────────────────────────────

async function initChat() {
  const panel = document.getElementById('tab-chat');
  panel.innerHTML = getChatHTML();

  // Load models into selector
  try {
    const data = await apiFetch('/models');
    const select = document.getElementById('model-select');
    if (select && data.models) {
      select.innerHTML = data.models.map(m =>
        `<option value="${escapeHtml(m.id)}">${escapeHtml(m.display)}</option>`
      ).join('');
    }
  } catch (e) {
    console.warn('Could not load models:', e.message);
  }

  // Load conversation list
  await loadConversationList();

  // Wire up events
  document.getElementById('chat-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  document.getElementById('model-select')?.addEventListener('change', e => {
    chatState.model = e.target.value;
  });
}

function getChatHTML() {
  return `
    <div class="chat-layout">
      <div class="chat-sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">History</span>
          <button class="btn btn-sm btn-outline" onclick="newConversation()">+ New</button>
        </div>
        <div id="conversation-list" class="conversation-list">
          <div class="loading-small">Loading…</div>
        </div>
      </div>

      <div class="chat-main">
        <div class="chat-toolbar">
          <label class="toolbar-label">Model</label>
          <select id="model-select" class="model-select">
            <option value="auto">⚡ Auto (best available)</option>
          </select>
          <button class="btn btn-sm btn-outline" onclick="clearCurrentChat()">Clear</button>
        </div>

        <div id="chat-messages" class="chat-messages">
          <div class="chat-welcome">
            <strong>FreeRouter Chat</strong>
            <p>Messages auto-route to your best available provider.<br>
            Each response shows the provider and model used.<br>
            History is saved locally and persists after restart.</p>
          </div>
        </div>

        <div class="chat-input-row">
          <textarea id="chat-input" class="chat-input"
            placeholder="Type a message… (Enter to send, Shift+Enter for newline)" rows="3"></textarea>
          <button id="send-btn" class="btn btn-primary" onclick="sendMessage()">Send</button>
        </div>
      </div>
    </div>
  `;
}

// ─── Conversation list ────────────────────────────────────────────────────────

async function loadConversationList() {
  try {
    const data = await apiFetch('/conversations');
    const convs = data.conversations || [];
    const list = document.getElementById('conversation-list');
    if (!list) return;

    if (convs.length === 0) {
      list.innerHTML = '<div class="sidebar-empty">No conversations yet</div>';
      return;
    }

    list.innerHTML = convs.map(c => `
      <div class="conv-item ${c.id === chatState.conversationId ? 'active' : ''}"
           onclick="loadConversation('${c.id}')">
        <div class="conv-title">${escapeHtml(c.title || 'Untitled')}</div>
        <div class="conv-meta">${c.message_count || 0} messages</div>
        <button class="conv-delete" onclick="deleteConv(event, '${c.id}')">×</button>
      </div>
    `).join('');
  } catch (e) {
    console.warn('Could not load conversations:', e.message);
  }
}

async function newConversation() {
  const data = await apiFetch('/conversations', { method: 'POST', body: JSON.stringify({}) });
  chatState.conversationId = data.id;
  chatState.messages = [];
  const container = document.getElementById('chat-messages');
  if (container) container.innerHTML = `
    <div class="chat-welcome"><strong>New conversation</strong><p>Start typing below.</p></div>
  `;
  await loadConversationList();
}

async function loadConversation(cid) {
  try {
    const conv = await apiFetch(`/conversations/${cid}`);
    chatState.conversationId = cid;
    chatState.messages = conv.messages || [];

    const container = document.getElementById('chat-messages');
    if (!container) return;

    if (conv.messages.length === 0) {
      container.innerHTML = `<div class="chat-welcome"><strong>${escapeHtml(conv.title)}</strong><p>No messages yet.</p></div>`;
    } else {
      container.innerHTML = conv.messages.map(m => renderMessageHTML(m)).join('');
    }
    container.scrollTop = container.scrollHeight;
    await loadConversationList();
  } catch (e) {
    showToast('Could not load conversation: ' + e.message, 'error');
  }
}

async function deleteConv(event, cid) {
  event.stopPropagation();
  if (!confirm('Delete this conversation?')) return;
  try {
    await apiFetch(`/conversations/${cid}`, { method: 'DELETE' });
    if (chatState.conversationId === cid) {
      chatState.conversationId = null;
      chatState.messages = [];
      document.getElementById('chat-messages').innerHTML = `
        <div class="chat-welcome"><strong>Conversation deleted</strong><p>Start a new one.</p></div>
      `;
    }
    await loadConversationList();
  } catch (e) {
    showToast('Delete failed: ' + e.message, 'error');
  }
}

function clearCurrentChat() {
  chatState.messages = [];
  chatState.conversationId = null;
  const container = document.getElementById('chat-messages');
  if (container) container.innerHTML = `
    <div class="chat-welcome"><strong>Cleared</strong><p>Start a new conversation.</p></div>
  `;
}

// ─── Send ─────────────────────────────────────────────────────────────────────

async function sendMessage() {
  if (chatState.isStreaming) return;
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  // Create a new conversation automatically if none exists
  if (!chatState.conversationId) {
    const data = await apiFetch('/conversations', {
      method: 'POST',
      body: JSON.stringify({ model: chatState.model }),
    });
    chatState.conversationId = data.id;
  }

  input.value = '';
  chatState.isStreaming = true;
  document.getElementById('send-btn').disabled = true;

  const userMsg = { role: 'user', content: text, timestamp: new Date().toISOString() };
  chatState.messages.push(userMsg);
  appendMessage(userMsg);

  // Save user message to DB
  try {
    await apiFetch(`/conversations/${chatState.conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ role: 'user', content: text }),
    });
  } catch (e) { console.warn('Could not save user message:', e.message); }

  const assistantId = 'msg-' + Date.now();
  appendStreamingPlaceholder(assistantId);

  try {
    const model = document.getElementById('model-select')?.value || 'auto';
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        messages: chatState.messages.map(m => ({ role: m.role, content: m.content })),
        temperature: 0.7,
        max_tokens: 4096,
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const { content, provider, model: usedModel } = await readStream(response, assistantId);

    const assistantMsg = {
      role: 'assistant', content: content || '(no response)',
      timestamp: new Date().toISOString(), provider, model: usedModel,
    };
    chatState.messages.push(assistantMsg);
    finalizeMessage(assistantId, assistantMsg);

    // Save assistant message to DB with provider info
    try {
      await apiFetch(`/conversations/${chatState.conversationId}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          role: 'assistant', content: assistantMsg.content,
          provider, model: usedModel,
        }),
      });
      await loadConversationList(); // refresh sidebar title
    } catch (e) { console.warn('Could not save assistant message:', e.message); }

  } catch (e) {
    setMessageError(assistantId, e.message);
    showToast('Error: ' + e.message, 'error');
  } finally {
    chatState.isStreaming = false;
    document.getElementById('send-btn').disabled = false;
    document.getElementById('chat-input')?.focus();
  }
}

// ─── SSE Stream Reader ────────────────────────────────────────────────────────

async function readStream(response, elementId) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let fullContent = '', buffer = '', provider = '', usedModel = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data: ')) continue;
      const data = trimmed.slice(6);
      if (data === '[DONE]' || !data) continue;
      try {
        const parsed = JSON.parse(data);
        if (parsed.error) throw new Error(typeof parsed.error === 'string' ? parsed.error : parsed.error.message || 'Error');
        if (parsed.meta?._provider) {
          provider = parsed.meta._provider;
          usedModel = parsed.meta._model || '';
          updateStreamingProvider(elementId, provider, usedModel);
          continue;
        }
        const delta = parsed.choices?.[0]?.delta?.content;
        if (delta) { fullContent += delta; updateStreamingMessage(elementId, fullContent); }
      } catch (e) {
        if (e.message && !e.message.includes('JSON')) throw e;
      }
    }
  }
  return { content: fullContent, provider, model: usedModel };
}

// ─── DOM helpers ──────────────────────────────────────────────────────────────

function renderMessageHTML(msg) {
  const providerTag = (msg.role === 'assistant' && msg.provider)
    ? `<span class="provider-tag">${escapeHtml(msg.provider)}${msg.model ? ' / ' + escapeHtml(msg.model) : ''}</span>`
    : '';
  return `
    <div class="chat-msg ${msg.role}">
      <div class="msg-header">
        ${msg.role === 'user' ? 'You' : 'Assistant'}
        ${providerTag}
        <span class="msg-time">${formatTime(msg.timestamp)}</span>
      </div>
      <div class="msg-body">${escapeHtml(msg.content)}</div>
    </div>
  `;
}

function appendMessage(msg) {
  const container = document.getElementById('chat-messages');
  container.querySelector('.chat-welcome')?.remove();
  container.insertAdjacentHTML('beforeend', renderMessageHTML(msg));
  container.scrollTop = container.scrollHeight;
}

function appendStreamingPlaceholder(id) {
  const container = document.getElementById('chat-messages');
  container.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="chat-msg assistant streaming">
      <div class="msg-header">Assistant <span class="provider-tag" id="${id}-provider">routing…</span></div>
      <div class="msg-body"><span class="thinking-dots">thinking</span></div>
    </div>
  `);
  container.scrollTop = container.scrollHeight;
}

function updateStreamingProvider(id, provider, model) {
  const el = document.getElementById(`${id}-provider`);
  if (el) el.textContent = `${provider}${model ? ' / ' + model : ''}`;
}

function updateStreamingMessage(id, content) {
  const el = document.getElementById(id);
  if (!el) return;
  el.querySelector('.msg-body').textContent = content;
  document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;
}

function finalizeMessage(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('streaming');
  const providerTag = msg.provider
    ? `<span class="provider-tag">${escapeHtml(msg.provider)}${msg.model ? ' / ' + escapeHtml(msg.model) : ''}</span>`
    : '';
  el.querySelector('.msg-header').innerHTML = `Assistant ${providerTag} <span class="msg-time">${formatTime(msg.timestamp)}</span>`;
  el.querySelector('.msg-body').textContent = msg.content;
}

function setMessageError(id, errorText) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('streaming');
  el.querySelector('.msg-header').innerHTML = 'Assistant <span class="provider-tag error-tag">failed</span>';
  el.querySelector('.msg-body').innerHTML = `<span class="text-err">Error: ${escapeHtml(errorText)}</span>`;
}
