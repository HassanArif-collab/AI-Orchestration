/**
 * chat.js — Chat tab: streaming conversations with any configured provider.
 *
 * Context: Core chat UI. Sends messages to /api/chat/stream which routes
 * directly to the best available provider via Router. No LiteLLM needed.
 *
 * How streaming works:
 *   1. POST to /api/chat/stream with messages array
 *   2. Server returns SSE stream of OpenAI-format chunks
 *   3. We parse each "data: {...}" line and append delta content
 *   4. On [DONE] or stream end, save message to conversation
 *
 * State: chatState (model, conversationId, messages, isStreaming)
 * Depends on: ui.js (apiFetch, showToast, escapeHtml, formatTime)
 */

const chatState = {
  model: 'auto',
  conversationId: null,
  messages: [],
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

  // Wire up send button and Enter key
  const input = document.getElementById('chat-input');
  if (input) {
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
  }

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
          <p>Select a model above and start chatting. Add API keys in the Providers tab first.</p>
        </div>
      </div>

      <div class="chat-input-row">
        <textarea id="chat-input" class="chat-input" placeholder="Type a message… (Enter to send, Shift+Enter for newline)" rows="3"></textarea>
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

  // Add user message to UI
  const userMsg = { role: 'user', content: text, timestamp: new Date().toISOString() };
  chatState.messages.push(userMsg);
  appendMessage(userMsg);

  // Add streaming placeholder for assistant
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

    const fullContent = await readStream(response, assistantId);

    // Save assistant message
    const assistantMsg = {
      role: 'assistant',
      content: fullContent || '(no response)',
      timestamp: new Date().toISOString(),
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
  let providerUsed = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.startsWith('data: ')) continue;

      const data = trimmed.slice(6);
      if (data === '[DONE]' || data === '') continue;

      try {
        const parsed = JSON.parse(data);

        // Check for error
        if (parsed.error) {
          throw new Error(typeof parsed.error === 'string' ? parsed.error : parsed.error.message || 'Provider error');
        }

        // Grab provider metadata from first chunk
        if (parsed.meta?._provider && !providerUsed) {
          providerUsed = parsed.meta._provider;
        }

        // Extract delta content
        const delta = parsed.choices?.[0]?.delta?.content;
        if (delta) {
          fullContent += delta;
          updateStreamingMessage(elementId, fullContent);
        }
      } catch (e) {
        if (e.message.includes('Provider') || e.message.includes('error')) throw e;
        // Skip unparseable lines silently
      }
    }
  }

  return fullContent;
}

// ─── DOM Helpers ──────────────────────────────────────────────────────────────

function appendMessage(msg) {
  const container = document.getElementById('chat-messages');
  // Remove welcome message on first real message
  container.querySelector('.chat-welcome')?.remove();

  const div = document.createElement('div');
  div.className = `chat-msg ${msg.role}`;
  div.innerHTML = `
    <div class="msg-header">${msg.role === 'user' ? 'You' : 'Assistant'} <span class="msg-time">${formatTime(msg.timestamp)}</span></div>
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
    <div class="msg-header">Assistant</div>
    <div class="msg-body"><span class="thinking-dots">thinking</span></div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
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
  el.querySelector('.msg-header').innerHTML = `Assistant <span class="msg-time">${formatTime(msg.timestamp)}</span>`;
  el.querySelector('.msg-body').textContent = msg.content;
}

function setMessageError(id, errorText) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('streaming');
  el.classList.add('error');
  el.querySelector('.msg-body').innerHTML = `<span class="text-err">Error: ${escapeHtml(errorText)}</span>`;
}

function clearChat() {
  chatState.messages = [];
  const container = document.getElementById('chat-messages');
  if (container) {
    container.innerHTML = `
      <div class="chat-welcome">
        <strong>Chat cleared</strong>
        <p>Start a new conversation.</p>
      </div>
    `;
  }
}
