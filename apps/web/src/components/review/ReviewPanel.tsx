import { useState } from 'react';
import { CheckCircle, RotateCcw, Loader2, AlertTriangle } from 'lucide-react';
import { resumePipeline } from '@/lib/api';
import { mapApiError } from '@/lib/errorMapper';
import { showToast } from '@/hooks/useToast';
import { cn } from '@/lib/utils';
import { PublishConfirmModal } from './PublishConfirmModal';

interface Props {
  cardId: string;
  cardTitle?: string;
  cardScore?: number | null;
  cardIterationCount?: number;
  cardContent?: string;
  cardVisualPlan?: string;
  onDecision: () => void;
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
  const [feedbackError, setFeedbackError] = useState('');

  const handleFeedbackChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setFeedback(value);
    if (feedbackError && value.trim().length >= 10) {
      setFeedbackError('');
    }
  };

  const getFeedbackError = (): string => {
    if (feedbackError) return feedbackError;
    if (confirmationState === 'error' && errorMessage) return errorMessage;
    return '';
  };

  const handleReject = async () => {
    if (!feedback.trim()) {
      setFeedbackError('Please provide feedback so the AI knows what to fix.');
      return;
    }
    if (feedback.trim().length < 10) {
      setFeedbackError('Feedback should be at least 10 characters to be useful.');
      return;
    }

    setConfirmationState('submitting');
    setErrorMessage('');
    setFeedbackError('');

    try {
      await resumePipeline(cardId, { approved: false, feedback: feedback.trim() });

      setConfirmationState('idle');
      showToast({ type: 'info', title: 'Script rejected', message: 'Moving back to revision queue' });
      onDecision();
    } catch (err) {
      setConfirmationState('error');
      setFeedbackError('');
      const friendlyError = mapApiError(err);
      setErrorMessage(friendlyError.message);
    }
  };

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
    setFeedbackError('');

    try {
      await resumePipeline(cardId, { approved: true });

      setConfirmationState('idle');
      setShowPublishConfirm(false);
      showToast({ type: 'success', title: 'Script approved', message: 'Publishing to Notion...' });
      onDecision();
    } catch (err) {
      setConfirmationState('error');
      setShowPublishConfirm(false);
      setFeedbackError('');
      const friendlyError = mapApiError(err);
      setErrorMessage(friendlyError.message);
    }
  };

  return (
    <>
      <div className="p-4 bg-amber-500/10 border-t border-amber-500/20">
        <h3 className="text-sm font-semibold text-amber-400 mb-2 flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4" strokeWidth={1.5} />
          Human Review Required
        </h3>
        <p className="text-xs text-[hsl(var(--neutral-400))] mb-3">
          Review the script and visual cues above. Approve to publish to Notion,
          or provide feedback to send back for revision.
        </p>

        {getFeedbackError() && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 text-sm mb-4">
            <p className="text-red-300 font-medium flex items-center gap-2">
              <AlertTriangle className="w-3 h-3" strokeWidth={1.5} />
              Could not submit your decision
            </p>
            <p className="text-red-200/70 mt-1">{getFeedbackError()}</p>
            <p className="text-red-200/50 mt-1 text-xs">
              Your decision was not saved. Please try again.
            </p>
          </div>
        )}

        <textarea
          value={feedback}
          onChange={handleFeedbackChange}
          placeholder="What should be improved? Be specific..."
          className={cn(
            'w-full bg-[hsl(var(--neutral-800))] border rounded-xl p-2.5 text-sm',
            'text-[hsl(var(--neutral-100))] placeholder-[hsl(var(--neutral-500))]',
            'resize-none h-20 transition-colors',
            'focus:outline-none focus:ring-2',
            getFeedbackError()
              ? 'border-red-500 focus:ring-red-400'
              : 'border-[hsl(var(--surface-glass-border))] focus:ring-[hsl(var(--brand-500))]',
          )}
        />
        <p className="text-[hsl(var(--neutral-500))] text-xs mt-1 text-right">
          {feedback.length} characters
        </p>

        <div className="flex gap-3 mt-3">
          <button
            onClick={handleApprove}
            disabled={confirmationState === 'submitting'}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5',
              'bg-emerald-600 hover:bg-emerald-500 text-white',
              'py-2.5 rounded-xl text-sm font-medium transition-all',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400',
              confirmationState === 'submitting' && 'opacity-50 cursor-not-allowed',
            )}
          >
            {confirmationState === 'submitting' ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.5} />
                <span>Confirming...</span>
              </>
            ) : (
              <>
                <CheckCircle className="w-3.5 h-3.5" strokeWidth={1.5} />
                <span>Approve & Publish</span>
              </>
            )}
          </button>
          <button
            onClick={handleReject}
            disabled={confirmationState === 'submitting'}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5',
              'bg-red-600 hover:bg-red-500 text-white',
              'py-2.5 rounded-xl text-sm font-medium transition-all',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400',
              confirmationState === 'submitting' && 'opacity-50 cursor-not-allowed',
            )}
          >
            {confirmationState === 'submitting' ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" strokeWidth={1.5} />
                <span>Confirming...</span>
              </>
            ) : (
              <>
                <RotateCcw className="w-3.5 h-3.5" strokeWidth={1.5} />
                <span>Revise</span>
              </>
            )}
          </button>
        </div>
      </div>

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
