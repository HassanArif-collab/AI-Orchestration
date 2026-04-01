/**
 * Global toast notification system.
 *
 * Uses a module-level store so any component can call `showToast()`
 * without needing to thread props or context through the tree.
 * The <ToastContainer /> component reads from this same store.
 */

import { useSyncExternalStore } from 'react';

// ── Types ──

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message: string;
}

type Listener = () => void;

// ── Module-level store (global singleton) ──

let toasts: Toast[] = [];
const listeners = new Set<Listener>();

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

function addToast(toast: Omit<Toast, 'id'>): string {
  const id = Date.now().toString() + Math.random().toString(36).slice(2, 6);
  toasts = [...toasts, { ...toast, id }];

  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    dismissToast(id);
  }, 5000);

  emitChange();
  return id;
}

function dismissToast(id: string) {
  toasts = toasts.filter((t) => t.id !== id);
  emitChange();
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
