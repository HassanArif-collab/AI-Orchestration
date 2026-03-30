import type { KanbanCard } from '../../types';
import { StatusBadge } from '../common/StatusBadge';
import { useCardTimer } from '../../hooks/useCardTimer';
import { api } from '../../lib/api';

interface Props {
  card: KanbanCard;
  onClick: () => void;
}

export function Card({ card, onClick }: Props) {
  const timer = useCardTimer(card.column === 2 ? card.expires_at : null);

  const handleSave = async (e: React.MouseEvent) => {
    e.stopPropagation(); // Don't trigger onClick (drawer open)
    try {
      await api.saveCard(card.id);
    } catch (err) {
      console.error('Failed to save card:', err);
    }
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this topic?')) {
      try {
        await api.deleteCard(card.id);
      } catch (err) {
        console.error('Failed to delete card:', err);
      }
    }
  };

  const handleStartPipeline = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.produce(card.id);
    } catch (err) {
      console.error('Failed to start pipeline:', err);
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

      {/* Column 2 specific: Timer + Save/Dismiss buttons */}
      {card.column === 2 && !timer.isExpired && (
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

          {/* Action buttons */}
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              className="flex-1 text-xs bg-green-600 hover:bg-green-500 text-white px-2 py-1 rounded"
            >
              ✓ Save
            </button>
            <button
              onClick={handleDelete}
              className="flex-1 text-xs bg-gray-600 hover:bg-gray-500 text-white px-2 py-1 rounded"
            >
              ✗ Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Column 2: "Start Pipeline" button (only on saved cards) */}
      {card.column === 2 && card.status === 'suggested' && (
        <button
          onClick={handleStartPipeline}
          className="mt-2 w-full text-xs bg-blue-600 hover:bg-blue-500 text-white py-1.5 rounded font-medium"
        >
          🚀 Start Pipeline
        </button>
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
