import { useState, useEffect, useRef } from 'react';

/**
 * Publish confirmation modal shown before approving a script for Notion.
 *
 * Features:
 * - Script preview with title, score, iteration count, and snippet
 * - Visual plan preview (if available)
 * - 5-second countdown on the publish button to prevent accidental clicks
 * - "Don't show this again" checkbox persisted in localStorage
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
        className="relative bg-gray-900 border border-gray-700 rounded-lg shadow-2xl max-w-2xl w-full mx-4 p-6 animate-scale-in"
      >
        <h2 className="text-2xl font-bold text-white mb-4">
          📤 Ready to Publish to Notion?
        </h2>

        {/* Script Preview */}
        <div className="bg-gray-800 border border-gray-700 rounded p-4 mb-4">
          <h3 className="text-lg font-semibold text-white mb-2">
            {scriptPreview.title}
          </h3>
          <div className="flex items-center gap-4 text-sm text-gray-400 mb-3">
            <span>Score: {scriptPreview.score.toFixed(1)}/10</span>
            <span>•</span>
            <span>Iteration {scriptPreview.iterationCount}</span>
          </div>
          <p className="text-gray-300 text-sm line-clamp-3">
            {scriptPreview.snippet}
          </p>
        </div>

        {/* Visual Preview (if available) */}
        {visualSnippet && (
          <div className="bg-gray-800 border border-gray-700 rounded p-4 mb-4">
            <p className="text-sm text-gray-400 mb-2">Visual Plan Preview:</p>
            <div className="bg-gray-900 rounded p-2 text-xs text-gray-300 font-mono max-h-32 overflow-y-auto">
              {visualSnippet}
            </div>
          </div>
        )}

        {/* Warning */}
        <div className="bg-yellow-900/20 border border-yellow-600/50 rounded p-3 mb-4">
          <p className="text-yellow-300 text-sm">
            ⚠ This action will publish the script to your Notion workspace and cannot be undone.
          </p>
        </div>

        {/* Suppress future checkbox */}
        <label className="flex items-center gap-2 text-sm text-gray-400 mb-6 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={suppressFuture}
            onChange={(e) => setSuppressFuture(e.target.checked)}
            className="rounded"
          />
          <span>Don't show this confirmation again</span>
        </label>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 bg-gray-700 hover:bg-gray-600 text-white px-6 py-3 rounded-lg font-medium transition-colors"
          >
            ← Keep Editing
          </button>
          <button
            onClick={handleConfirm}
            disabled={countdown > 0}
            className={`flex-1 px-6 py-3 rounded-lg font-medium transition-all ${
              countdown > 0
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-green-600 hover:bg-green-700 text-white'
            }`}
          >
            {countdown > 0 ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-pulse">📤</span>
                <span>Publish to Notion ({countdown}s)</span>
              </span>
            ) : (
              '📤 Publish to Notion'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
