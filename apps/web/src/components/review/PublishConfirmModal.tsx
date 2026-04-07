import { useState, useEffect, useRef } from 'react';

/**
 * Publish confirmation modal shown before approving a script for Notion.
 *
 * Features:
 * - Script preview with title, score, iteration count, and snippet
 * - Visual plan preview (if available)
 * - 5-second countdown on the publish button to prevent accidental clicks
 * - "Don't show this again" checkbox persisted in localStorage
 * - Full ARIA dialog attributes (role, aria-modal, focus trap)
 * - Escape key handler
 */

interface PublishConfirmModalProps {
  isOpen: boolean;
  scriptPreview: {
    title: string;
    score: number;
    iterationCount: number;
    snippet: string;
  };
  visualSnippet?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function PublishConfirmModal({
  isOpen,
  scriptPreview,
  visualSnippet,
  onConfirm,
  onCancel,
}: PublishConfirmModalProps) {
  const [countdown, setCountdown] = useState(5);
  const [suppressFuture, setSuppressFuture] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setCountdown(5);
      return;
    }

    if (countdown === 0) return;

    const timer = setInterval(() => {
      setCountdown((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen, countdown]);

  const handleConfirm = () => {
    if (suppressFuture) {
      localStorage.setItem('suppressPublishModal', 'true');
    }
    onConfirm();
  };

  // Escape key handler
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onCancel]);

  // Focus trap + auto-focus when modal opens
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen || !modalRef.current) return;

    const modal = modalRef.current;
    const focusableSelector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

    const getFocusableElements = (): HTMLElement[] => {
      return Array.from(modal.querySelectorAll(focusableSelector)) as HTMLElement[];
    };

    // Auto-focus the "Keep Editing" button
    const focusables = getFocusableElements();
    const keepEditingBtn = modal.querySelector('button'); // first button is "Keep Editing"
    const initialFocus = keepEditingBtn instanceof HTMLElement ? keepEditingBtn : focusables[0];
    initialFocus?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      const elements = getFocusableElements();
      if (elements.length === 0) {
        e.preventDefault();
        return;
      }

      const first = elements[0];
      const last = elements[elements.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    modal.addEventListener('keydown', handleKeyDown);
    return () => modal.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Modal */}
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-label="Confirm publish"
        className="relative bg-[hsl(var(--surface-sunken)/0.95)] backdrop-blur-3xl border border-[hsl(var(--surface-glass-border))] rounded-2xl shadow-2xl max-w-2xl w-full mx-4 p-6"
      >
        <h2 className="text-xl font-bold text-[hsl(var(--neutral-100))] mb-4 flex items-center gap-2">
          <span className="text-lg">&#x1F4E4;</span>
          Ready to Publish to Notion?
        </h2>

        {/* Script Preview */}
        <div className="bg-[hsl(var(--surface-glass))] border border-[hsl(var(--surface-glass-border))] rounded-xl p-4 mb-4">
          <h3 className="text-lg font-semibold text-[hsl(var(--neutral-100))] mb-2">
            {scriptPreview.title}
          </h3>
          <div className="flex items-center gap-4 text-sm text-[hsl(var(--neutral-400))] mb-3">
            <span>Score: {scriptPreview.score.toFixed(1)}%</span>
            <span>&middot;</span>
            <span>Iteration {scriptPreview.iterationCount}</span>
          </div>
          <p className="text-[hsl(var(--neutral-300))] text-sm line-clamp-3">
            {scriptPreview.snippet}
          </p>
        </div>

        {/* Visual Preview (if available) */}
        {visualSnippet && (
          <div className="bg-[hsl(var(--surface-glass))] border border-[hsl(var(--surface-glass-border))] rounded-xl p-4 mb-4">
            <p className="text-sm text-[hsl(var(--neutral-400))] mb-2">Visual Plan Preview:</p>
            <div className="bg-[hsl(var(--neutral-800)/0.5)] rounded-lg p-3 text-xs text-[hsl(var(--lineage-cyan))] font-mono max-h-32 overflow-y-auto">
              {visualSnippet}
            </div>
          </div>
        )}

        {/* Warning */}
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 mb-4">
          <p className="text-amber-300 text-sm">
            <span className="mr-1">&#x26A0;</span>
            This action will publish the script to your Notion workspace and cannot be undone.
          </p>
        </div>

        {/* Suppress future checkbox */}
        <label className="flex items-center gap-2 text-sm text-[hsl(var(--neutral-400))] mb-6 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={suppressFuture}
            onChange={(e) => setSuppressFuture(e.target.checked)}
            className="rounded"
          />
          <span>Don&apos;t show this confirmation again</span>
        </label>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 bg-[hsl(var(--neutral-800))] hover:bg-[hsl(var(--neutral-700))] text-[hsl(var(--neutral-100))] px-6 py-3 rounded-xl font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]"
          >
            Keep Editing
          </button>
          <button
            onClick={handleConfirm}
            disabled={countdown > 0}
            className={cn(
              'flex-1 px-6 py-3 rounded-xl font-medium transition-all',
              countdown > 0
                ? 'bg-[hsl(var(--neutral-800))] text-[hsl(var(--neutral-500))] cursor-not-allowed'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400',
            )}
          >
            {countdown > 0 ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-pulse">&#x1F4E4;</span>
                <span>Publish to Notion ({countdown}s)</span>
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <span>&#x1F4E4;</span>
                Publish to Notion
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(' ');
}
