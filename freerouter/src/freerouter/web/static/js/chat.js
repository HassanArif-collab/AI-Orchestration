/**
 * chat.js — Chat tab: streaming conversations with provider visibility.
 *
 * Context: Core chat UI. Shows which provider/model handled each response.
 * Sends to /api/chat/stream → Router → best available provider.
 * If a provider fails, Router automatically tries the next one.
 *
 * Depends on: ui.js (apiFetch, showToast, escapeHtml, formatTime)
 */

const chatState = {
  model: 'auto',
  messages: [],
  isStreaming: false,
};

// ─── Init ─────────────────────────────────────────────────────────────────────

async function initChat() {
  const panel = document.getElementById('tab-chat');
  panel.innerHTML = getChatHTML();

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
      <div class="chat-toolbar">
        <label class="toolbar-label">Model</label>
        <select id="model-select" class="model-select">
          <option value="auto">⚡ Auto (best available)</option>
        </select>
        <button class="btn btn-sm btn-outline" onclick="clearChat()">Clear</button>
      </div>

      <div id="chat-messages" class="chat-messages">
        <div class="chat-welcome">
          <strong>FreeRouter Chat</strong>
          <p>Messages automatically route to your best available provider.<br>
          Each response shows which provider and model handled it.</p>
        </div>
      </div>

      <div class="chat-input-row">
        <textarea id="chat-input" class="chat-input"
          placeholder="Type a message… (Enter to send, Shift+Enter for newline)" rows="3"></textarea>
        <button id="send-btn" class="btn btn-primary" onclick="sendMessage()">Send</button>
      </div>
    </div>
  `;
}

// ─── Send ─────────────────────────────────────────────────────────────────────

async function sendMessage() {
  if (chatState.isStreaming) return;

  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  chatState.isStreaming = true;
  document.getElementById('send-btn').disabled = true;

  const userMsg = { role: 'user', content: text, timestamp: new Date().toISOString() };
  chatState.messages.push(userMsg);
  appendMessage(userMsg);

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
      role: 'assistant',
      content: content || '(no response)',
      timestamp: new Date().toISOString(),
      provider,
      model: usedModel,
    };
    chatState.messages.push(assistantMsg);
    finalizeMessage(assistantId, assistantMsg);

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
  let fullContent = '';
  let buffer = '';
  let provider = '';
  let usedModel = '';

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
      if (data === '[DONE]' || data === '') continue;

      try {
        const parsed = JSON.parse(data);

        // Error from provider
        if (parsed.error) {
          const errText = typeof parsed.error === 'string' ? parsed.error : parsed.error.message || 'Error';
          throw new Error(errText);
        }

        // Meta chunk — grab provider info
        if (parsed.meta?._provider) {
          provider = parsed.meta._provider;
          usedModel = parsed.meta._model || '';
          // Update the placeholder header to show provider
          updateStreamingProvider(elementId, provider, usedModel);
          continue;
        }

        // Content delta
        const delta = parsed.choices?.[0]?.delta?.content;
        if (delta) {
          fullContent += delta;
          updateStreamingMessage(elementId, fullContent);
        }
      } catch (e) {
        if (e.message && !e.message.includes('JSON')) throw e;
      }
    }
  }

  return { content: fullContent, provider, model: usedModel };
}

// ─── DOM Helpers ──────────────────────────────────────────────────────────────

function appendMessage(msg) {
  const container = document.getElementById('chat-messages');
  container.querySelector('.chat-welcome')?.remove();

  const div = document.createElement('div');
  div.className = `chat-msg ${msg.role}`;

  const providerTag = (msg.role === 'assistant' && msg.provider)
    ? `<span class="provider-tag">${escapeHtml(msg.provider)}${msg.model ? ' / ' + escapeHtml(msg.model) : ''}</span>`
    : '';

  div.innerHTML = `
    <div class="msg-header">
      ${msg.role === 'user' ? 'You' : 'Assistant'}
      ${providerTag}
      <span class="msg-time">${formatTime(msg.timestamp)}</span>
    </div>
    <div class="msg-body">${escapeHtml(msg.content)}</div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendStreamingPlaceholder(id) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.id = id;
  div.className = 'chat-msg assistant streaming';
  div.innerHTML = `
    <div class="msg-header">Assistant <span class="provider-tag" id="${id}-provider">routing...</span></div>
    <div class="msg-body"><span class="thinking-dots">thinking</span></div>
  `;
  container.appendChild(div);
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

function clearChat() {
  chatState.messages = [];
  const container = document.getElementById('chat-messages');
  if (container) {
    container.innerHTML = `
      <div class="chat-welcome">
        <strong>Chat cleared</strong><p>Start a new conversation.</p>
      </div>`;
  }
}
