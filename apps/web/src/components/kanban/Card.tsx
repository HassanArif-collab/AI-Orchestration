import { useState } from 'react';
import type { KanbanCard } from '../../types';
import { StatusBadge } from '../common/StatusBadge';
import { useCardTimer } from '../../hooks/useCardTimer';
import { api } from '../../lib/api';
import { getCardAction } from '../../lib/cardHelpers';
import { showToast } from '../../hooks/useToast';
import { mapApiError } from '../../lib/errorMapper';

interface Props {
  card: KanbanCard;
  onClick: () => void;
}

export function Card({ card, onClick }: Props) {
  const timer = useCardTimer(card.column === 2 ? card.expires_at : null);
  const actionInfo = getCardAction(card);
  const [actionLoading, setActionLoading] = useState(false);

  const handleSave = async (e: React.MouseEvent) => {
    e.stopPropagation(); // Don't trigger onClick (drawer open)
    setActionLoading(true);
    try {
      await api.saveCard(card.id);
      showToast({
        type: 'success',
        title: 'Topic saved',
        message: 'The topic has been saved and will not expire.',
      });
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({
        type: 'error',
        title: 'Save failed',
        message: friendlyError.message,
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      await api.deleteCard(card.id);
      showToast({
        type: 'info',
        title: 'Topic dismissed',
        message: 'The topic has been removed.',
      });
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({
        type: 'error',
        title: 'Delete failed',
        message: friendlyError.message,
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartPipeline = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      await api.produce(card.id);
      showToast({
        type: 'success',
        title: 'Pipeline started',
        message: 'Production pipeline is now running.',
      });
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({
        type: 'error',
        title: 'Pipeline failed to start',
        message: friendlyError.message,
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleResubmit = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      await api.produce(card.id);
      showToast({
        type: 'success',
        title: 'Resubmitted',
        message: 'The card has been sent back to production.',
      });
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({
        type: 'error',
        title: 'Resubmit failed',
        message: friendlyError.message,
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleActionClick = (e: React.MouseEvent) => {
    switch (actionInfo.action) {
      case 'save':
        handleSave(e);
        break;
      case 'start_pipeline':
        handleStartPipeline(e);
        break;
      case 'review':
        onClick(); // Open drawer for review
        break;
      case 'resubmit':
        handleResubmit(e);
        break;
    }
  };

  return (
    <div
      onClick={onClick}
      className={`
        bg-gray-800 rounded-lg p-3 cursor-pointer
        border border-gray-700 hover:border-gray-500
        transition-all duration-200 hover:shadow-lg
        ${card.status === 'error' ? 'border-red-500/50' : ''}
        ${timer.isExpired ? 'opacity-40 pointer-events-none' : ''}
      `}
    >
      {/* Title */}
      <h4 className="text-sm font-medium text-white truncate">
        {card.topic_brief?.title ?? 'Untitled Topic'}
      </h4>

      {/* Description preview */}
      <p className="text-xs text-gray-400 mt-1 line-clamp-2">
        {card.topic_brief?.description ?? ''}
      </p>

      {/* Status + Score row */}
      <div className="flex items-center justify-between mt-2">
        <StatusBadge status={card.status} />
        {card.viability_score != null && (
          <span className="text-xs text-gray-500">
            Score: {card.viability_score}%
          </span>
        )}
      </div>

      {/* Column 2 specific: Timer countdown (only for expiring cards) */}
      {card.column === 2 && card.expires_at && !timer.isExpired && (
        <div className="mt-2 space-y-2">
          {/* Countdown bar */}
          <div className="w-full bg-gray-700 rounded-full h-1">
            <div
              className="bg-yellow-500 h-1 rounded-full transition-all duration-1000"
              style={{ width: `${100 - timer.percentage}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>⏱ {timer.remainingMinutes}m left</span>
          </div>
        </div>
      )}

      {/* Action button (from cardHelpers — replaces scattered conditionals) */}
      {actionInfo.action !== 'none' && (
        <div className="mt-2">
          {/* Contextual help text */}
          <p
            className={`text-xs mb-1.5 ${
              actionInfo.variant === 'success'
                ? 'text-green-400'
                : actionInfo.variant === 'warning'
                  ? 'text-yellow-400'
                  : actionInfo.variant === 'primary'
                    ? 'text-blue-400'
                    : 'text-gray-400'
            }`}
          >
            {actionInfo.reason}
          </p>

          {/* Action button */}
          <button
            onClick={handleActionClick}
            disabled={actionLoading}
            className={`w-full text-xs py-1.5 rounded font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
              actionInfo.variant === 'success'
                ? 'bg-green-600 hover:bg-green-500 text-white animate-pulse'
                : actionInfo.variant === 'warning'
                  ? 'bg-yellow-600 hover:bg-yellow-500 text-white'
                  : actionInfo.variant === 'primary'
                    ? 'bg-blue-600 hover:bg-blue-500 text-white'
                    : 'bg-gray-600 hover:bg-gray-500 text-white'
            }`}
          >
            {actionLoading ? '...' : actionInfo.label}
          </button>
        </div>
      )}

      {/* Non-actionable state message */}
      {actionInfo.action === 'none' && actionInfo.reason && (
        <p className="text-xs text-gray-500 mt-2 italic">
          {actionInfo.reason}
        </p>
      )}

      {/* Error message */}
      {card.error_message && (
        <p className="text-xs text-red-400 mt-2 truncate" title={card.error_message}>
          ⚠ {card.error_message}
        </p>
      )}
    </div>
  );
}
