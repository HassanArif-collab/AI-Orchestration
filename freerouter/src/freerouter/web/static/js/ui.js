/**
 * ui.js — Shared UI utilities: tabs, toast notifications, helpers.
 *
 * Context: Loaded first. Provides the tab system, toast messages,
 * and utility functions used by all other JS modules.
 *
 * Globals exposed: showToast(), switchTab(), escapeHtml(), formatTime()
 * Depends on: nothing (loaded first)
 */

// ─── Tab System ───────────────────────────────────────────────────────────────

function switchTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tabName));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('hidden', p.id !== 'tab-' + tabName));
  if (tabName === 'providers') loadProviders();
  if (tabName === 'chat') initChat();
  if (tabName === 'usage') loadUsage();
}

// ─── Toast ────────────────────────────────────────────────────────────────────

function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.classList.add('show'), 10);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatTime(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleTimeString(); } catch { return ''; }
}

async function apiFetch(path, options = {}) {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Wire up tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });
  // Load default tab
  switchTab('providers');
});
