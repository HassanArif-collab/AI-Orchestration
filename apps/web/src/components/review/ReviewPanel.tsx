import { useState } from 'react';
import { api } from '../../lib/api';
import { mapApiError } from '../../lib/errorMapper';
import { showToast } from '../../hooks/useToast';
import { PublishConfirmModal } from './PublishConfirmModal';

interface Props {
  cardId: string;
  cardTitle?: string;
  cardScore?: number | null;
  cardIterationCount?: number;
  cardContent?: string;
  cardVisualPlan?: string;
  onDecision: () => void; // Close drawer after decision
}

export function ReviewPanel({
  cardId,
  cardTitle,
  cardScore,
  cardIterationCount,
  cardContent,
  cardVisualPlan,
  onDecision,
}: Props) {
  const [feedback, setFeedback] = useState('');
  const [confirmationState, setConfirmationState] = useState<'idle' | 'submitting' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [showPublishConfirm, setShowPublishConfirm] = useState(false);

  // ── Reject (no confirmation modal needed) ──

  const handleReject = async () => {
    if (!feedback.trim()) {
      setConfirmationState('error');
      setErrorMessage('Please provide feedback so the AI knows what to fix.');
      return;
    }

    setConfirmationState('submitting');
    setErrorMessage('');

    try {
      await api.resume(cardId, { approved: false, feedback: feedback.trim() });

      setConfirmationState('idle');
      showToast({
        type: 'info',
        title: 'Script rejected',
        message: 'Moving back to revision queue',
      });
      onDecision();
    } catch (err) {
      setConfirmationState('error');
      const friendlyError = mapApiError(err);
      setErrorMessage(friendlyError.message);
    }
  };

  // ── Approve (two-phase: optional modal → API call) ──

  const handleApprove = () => {
    const suppressModal = localStorage.getItem('suppressPublishModal') === 'true';

    if (suppressModal) {
      executeApproval();
    } else {
      setShowPublishConfirm(true);
    }
  };

  const executeApproval = async () => {
    setConfirmationState('submitting');
    setErrorMessage('');

    try {
      await api.resume(cardId, { approved: true });

      setConfirmationState('idle');
      setShowPublishConfirm(false);
      showToast({
        type: 'success',
        title: '✅ Script approved',
        message: 'Publishing to Notion...',
      });
      onDecision();
    } catch (err) {
      setConfirmationState('error');
      setShowPublishConfirm(false);
      const friendlyError = mapApiError(err);
      setErrorMessage(friendlyError.message);
    }
  };

  return (
    <>
      <div className="p-4 bg-amber-900/20">
        <h3 className="text-sm font-semibold text-amber-400 mb-2">
          ⏸ Human Review Required
        </h3>
        <p className="text-xs text-gray-400 mb-3">
          Review the script and visual cues above. Approve to publish to Notion,
          or provide feedback to send back for revision.
        </p>

        {/* Inline error banner (shown on failure, keeps drawer open) */}
        {confirmationState === 'error' && (
          <div className="bg-red-900/30 border border-red-500 rounded p-3 text-sm mb-4 animate-shake">
            <p className="text-red-300 font-medium flex items-center gap-2">
              <span>⚠</span>
              <span>Could not submit your decision</span>
            </p>
            <p className="text-red-200/70 mt-1">{errorMessage}</p>
            <p className="text-red-200/50 mt-1 text-xs">
              Your decision was not saved. Please try again.
            </p>
          </div>
        )}

        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Feedback for revision (required if rejecting)..."
          className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white placeholder-gray-500 resize-none h-20 focus:outline-none focus:border-amber-500"
        />

        <div className="flex gap-3 mt-3">
          <button
            onClick={handleApprove}
            disabled={confirmationState === 'submitting'}
            className={`flex-1 bg-green-600 hover:bg-green-500 text-white py-2 rounded text-sm font-medium transition-all ${
              confirmationState === 'submitting' ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {confirmationState === 'submitting' ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-spin">⟳</span>
                <span>Confirming...</span>
              </span>
            ) : (
              '✅ Approve & Publish'
            )}
          </button>
          <button
            onClick={handleReject}
            disabled={confirmationState === 'submitting'}
            className={`flex-1 bg-red-600 hover:bg-red-500 text-white py-2 rounded text-sm font-medium transition-all ${
              confirmationState === 'submitting' ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {confirmationState === 'submitting' ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-spin">⟳</span>
                <span>Confirming...</span>
              </span>
            ) : (
              '🔄 Revise'
            )}
          </button>
        </div>
      </div>

      {/* Publish confirmation modal */}
      <PublishConfirmModal
        isOpen={showPublishConfirm}
        scriptPreview={{
          title: cardTitle ?? 'Untitled Script',
          score: cardScore ?? 0,
          iterationCount: cardIterationCount ?? 1,
          snippet: cardContent?.substring(0, 200) ?? 'No preview available',
        }}
        visualSnippet={cardVisualPlan?.substring(0, 300)}
        onConfirm={executeApproval}
        onCancel={() => setShowPublishConfirm(false)}
      />
    </>
  );
}
