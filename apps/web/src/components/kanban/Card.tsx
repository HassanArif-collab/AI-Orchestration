import { useState } from 'react';
import { useDraggable } from '@dnd-kit/core';
import type { KanbanCard } from '@/lib/schema';
import { StatusBadge } from '../common/StatusBadge';
import { useCardTimer } from '@/hooks/useCardTimer';
import { saveCard, startProduction } from '@/lib/api';
import { getCardAction } from '@/lib/cardHelpers';
import { showToast } from '@/hooks/useToast';
import { mapApiError } from '@/lib/errorMapper';

/** Extract topic_brief from card metadata safely */
function getTopicBrief(card: KanbanCard): { title?: string; description?: string } | null {
  const meta = card.metadata as Record<string, unknown> | undefined;
  if (!meta?.topic_brief) return null;
  const brief = meta.topic_brief as Record<string, unknown>;
  return {
    title: typeof brief.title === 'string' ? brief.title : undefined,
    description: typeof brief.description === 'string' ? brief.description : undefined,
  };
}

/** Extract viability_score from card metadata */
function getViabilityScore(card: KanbanCard): number | null {
  const meta = card.metadata as Record<string, unknown> | undefined;
  if (typeof meta?.viability_score !== 'number') return null;
  return meta.viability_score;
}

interface Props {
  card: KanbanCard;
  onClick: () => void;
}

export function Card({ card, onClick }: Props) {
  const timer = useCardTimer(card.column_index === 2 ? (card.expires_at ?? null) : null);
  const actionInfo = getCardAction(card);
  const [actionLoading, setActionLoading] = useState(false);
  const brief = getTopicBrief(card);
  const viabilityScore = getViabilityScore(card);

  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: card.id,
    data: { columnNumber: card.column_index },
  });

  const handleSave = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      await saveCard(card.id);
      showToast({
        type: 'success',
        title: 'Topic saved',
        message: 'The topic has been saved and will not expire.',
      });
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({ type: 'error', title: 'Save failed', message: friendlyError.message });
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartPipeline = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      await startProduction(card.id);
      showToast({ type: 'success', title: 'Pipeline started', message: 'Production pipeline is now running.' });
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({ type: 'error', title: 'Pipeline failed to start', message: friendlyError.message });
    } finally {
      setActionLoading(false);
    }
  };

  const handleResubmit = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      await startProduction(card.id);
      showToast({ type: 'success', title: 'Resubmitted', message: 'The card has been sent back to production.' });
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({ type: 'error', title: 'Resubmit failed', message: friendlyError.message });
    } finally {
      setActionLoading(false);
    }
  };

  const handleActionClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    switch (actionInfo.action) {
      case 'save':
        handleSave(e);
        break;
      case 'start_pipeline':
        handleStartPipeline(e);
        break;
      case 'review':
        onClick();
        break;
      case 'resubmit':
        handleResubmit(e);
        break;
    }
  };

  return (
    <div
      ref={setNodeRef}
      onClick={onClick}
      {...attributes}
      {...listeners}
      style={transform
        ? {
            transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
            opacity: isDragging ? 0.5 : 1,
          }
        : undefined
      }
      className={`
        bg-gray-800 rounded-lg p-3 cursor-pointer
        transition-all duration-200 hover:shadow-lg
        ${isDragging ? 'opacity-50 scale-95 ring-2 ring-blue-500/50' : ''}
        ${
          card.status === 'error'
            ? 'border border-red-500/50'
            : timer.isExpired
              ? 'border border-red-500/50 opacity-60'
              : timer.isCritical
                ? 'border border-orange-500 animate-pulse-border'
                : timer.isWarning
                  ? 'border border-yellow-600'
                  : 'border border-gray-700 hover:border-gray-500'
        }
      `}
    >
      {/* Title */}
      <h4 className="text-sm font-medium text-white truncate">
        {brief?.title ?? card.title ?? 'Untitled Topic'}
      </h4>

      {/* Description preview */}
      <p className="text-xs text-gray-400 mt-1 line-clamp-2">
        {brief?.description ?? ''}
      </p>

      {/* Status + Score row */}
      <div className="flex items-center justify-between mt-2">
        <StatusBadge status={card.status} />
        {viabilityScore != null && (
          <span className="text-xs text-gray-500">
            Score: {viabilityScore}%
          </span>
        )}
      </div>

      {/* Column 2: Timer countdown with progressive urgency */}
      {card.column_index === 2 && card.expires_at && (
        <div className="mt-2 space-y-1.5">
          <div className="w-full bg-gray-700 rounded-full h-1">
            <div
              className={`h-1 rounded-full transition-all duration-1000 ${
                timer.isCritical ? 'bg-orange-500' : timer.isWarning ? 'bg-yellow-500' : 'bg-green-500'
              }`}
              style={{ width: `${100 - timer.percentage}%` }}
            />
          </div>

          {timer.isExpired ? (
            <div className="flex items-center gap-1.5 text-xs text-red-400 font-medium">
              <span>⚠</span>
              <span>Expired — will be removed soon</span>
            </div>
          ) : timer.isCritical ? (
            <div className="flex items-center gap-1.5 text-xs text-orange-400 font-medium animate-pulse">
              <span>⏱</span>
              <span>Hurry! {timer.timeString} left</span>
            </div>
          ) : timer.isWarning ? (
            <div className="flex items-center gap-1.5 text-xs text-yellow-400">
              <span>⏱</span>
              <span>{timer.timeString} left — save to keep</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <span>⏱</span>
              <span>{timer.timeString} left</span>
            </div>
          )}
        </div>
      )}

      {/* Action button */}
      {actionInfo.action !== 'none' && (
        <div className="mt-2">
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
    </div>
  );
}
