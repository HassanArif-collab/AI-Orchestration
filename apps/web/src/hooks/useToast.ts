/**
 * Global toast notification system.
 *
 * Uses a module-level store so any component can call `showToast()`
 * without needing to thread props or context through the tree.
 * The <ToastContainer /> component reads from this same store.
 *
 * Toasts have a two-phase lifecycle:
 *   active → (dismiss) → dismissing → (300ms) → removed
 * This allows CSS exit animations before DOM removal.
 */

import { useSyncExternalStore } from 'react';

// ── Types ──

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message: string;
  status: 'active' | 'dismissing';
}

type Listener = () => void;

// ── Module-level store (global singleton) ──

let toasts: Toast[] = [];
const listeners = new Set<Listener>();
const autoDismissTimers = new Map<string, ReturnType<typeof setTimeout>>();

function emitChange() {
  for (const fn of listeners) fn();
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function getSnapshot(): Toast[] {
  return toasts;
}

// ── Actions ──

const EXIT_DURATION = 300; // ms — must match CSS animation duration

function addToast(toast: Omit<Toast, 'id' | 'status'>): string {
  const id = Date.now().toString() + Math.random().toString(36).slice(2, 6);
  const fullToast: Toast = { ...toast, id, status: 'active' };
  toasts = [...toasts, fullToast];

  // Auto-dismiss after 5 seconds
  const timer = setTimeout(() => {
    dismissToast(id);
    autoDismissTimers.delete(id);
  }, 5000);
  autoDismissTimers.set(id, timer);

  emitChange();
  return id;
}

function dismissToast(id: string) {
  const toast = toasts.find((t) => t.id === id);
  if (!toast || toast.status === 'dismissing') return;

  // Cancel auto-dismiss timer if manually dismissed
  autoDismissTimers.delete(id);

  // Phase 1: Mark as dismissing (triggers CSS exit animation)
  toasts = toasts.map((t) => t.id === id ? { ...t, status: 'dismissing' } : t);
  emitChange();

  // Phase 2: Remove from DOM after exit animation
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    emitChange();
  }, EXIT_DURATION);
}

// ── Public API ──

export { addToast as showToast, dismissToast };

// ── React hook ──

export function useToast() {
  const currentToasts = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  return {
    toasts: currentToasts,
    showToast: addToast,
    dismissToast,
  };
}
