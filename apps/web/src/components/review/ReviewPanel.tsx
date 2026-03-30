import { useState } from 'react';
import { api } from '../../lib/api';

interface Props {
  cardId: string;
  onDecision: () => void; // Close drawer after decision
}

export function ReviewPanel({ cardId, onDecision }: Props) {
  const [feedback, setFeedback] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleApprove = async () => {
    setIsSubmitting(true);
    try {
      await api.resume(cardId, { approved: true });
      onDecision();
    } catch (err) {
      console.error('Approve failed:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!feedback.trim()) {
      alert('Please provide feedback so the AI knows what to fix.');
      return;
    }
    setIsSubmitting(true);
    try {
      await api.resume(cardId, { approved: false, feedback: feedback.trim() });
      onDecision();
    } catch (err) {
      console.error('Reject failed:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-4 bg-amber-900/20">
      <h3 className="text-sm font-semibold text-amber-400 mb-2">
        ⏸ Human Review Required
      </h3>
      <p className="text-xs text-gray-400 mb-3">
        Review the script and visual cues above. Approve to publish to Notion, 
        or provide feedback to send back for revision.
      </p>

      <textarea
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        placeholder="Feedback for revision (required if rejecting)..."
        className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-sm text-white placeholder-gray-500 resize-none h-20"
      />

      <div className="flex gap-3 mt-3">
        <button
          onClick={handleApprove}
          disabled={isSubmitting}
          className="flex-1 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 text-white py-2 rounded text-sm font-medium"
        >
          {isSubmitting ? '...' : '✅ Approve & Publish'}
        </button>
        <button
          onClick={handleReject}
          disabled={isSubmitting}
          className="flex-1 bg-red-600 hover:bg-red-500 disabled:bg-gray-600 text-white py-2 rounded text-sm font-medium"
        >
          {isSubmitting ? '...' : '🔄 Revise'}
        </button>
      </div>
    </div>
  );
}
