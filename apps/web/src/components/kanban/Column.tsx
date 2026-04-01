import type { KanbanCard, ColumnDef } from '../../types';
import { Card } from './Card';
import { EmptyState } from '../common/EmptyState';
import { useDroppable } from '@dnd-kit/core';

interface Props {
  columnNumber: number;
  definition: ColumnDef;
  cards: KanbanCard[];
  onCardClick: (card: KanbanCard) => void;
  isDragging: boolean;
  dragErrorCardId: string | null;
  dragErrorMessage: string | null;
}

export function Column({
  columnNumber,
  definition,
  cards,
  onCardClick,
  isDragging,
  dragErrorCardId,
  dragErrorMessage,
}: Props) {
  // Make this column a valid drop target for drag-and-drop
  const { setNodeRef, isOver } = useDroppable({
    id: `column-${columnNumber}`,
    data: { columnNumber },
  });

  // Separate expired cards from active ones for accurate badge count
  const activeCards = cards.filter((card) => {
    if (!card.expires_at) return true;
    return new Date(card.expires_at) > new Date();
  });
  const expiredCount = cards.length - activeCards.length;

  return (
    <div
      ref={setNodeRef}
      className={`
        flex flex-col w-kanban-col min-w-[260px] shrink-0
        bg-gray-900 rounded-xl border
        ${isOver ? 'border-blue-500 bg-gray-800/50' : 'border-gray-800'}
        ${isDragging ? 'ring-1 ring-blue-500/30' : ''}
        transition-colors duration-200
      `}
    >
      {/* Column Header */}
      <div className="p-3 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">
            {definition.name}
          </h3>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            expiredCount > 0
              ? 'bg-yellow-900/50 text-yellow-300'
              : 'bg-gray-800 text-gray-500'
          }`}>
            {activeCards.length}
            {expiredCount > 0 && (
              <span className="text-yellow-500">+{expiredCount}</span>
            )}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-0.5">
          {definition.description}
        </p>
      </div>

      {/* Card List */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-2 max-h-[calc(100vh-180px)]">
        {cards.length === 0 ? (
          <EmptyState message="No cards" icon="📋" />
        ) : (
          cards.map((card) => (
            <div key={card.id} className="relative">
              <Card
                card={card}
                onClick={() => onCardClick(card)}
              />

              {/* Drag error overlay on the specific card */}
              {dragErrorCardId === card.id && dragErrorMessage && (
                <div className="absolute inset-0 bg-red-900/30 border-2 border-red-500 rounded-lg flex items-center justify-center animate-shake pointer-events-none">
                  <div className="bg-red-900 border border-red-500 rounded px-2 py-1.5 text-xs text-red-200 max-w-[90%] text-center">
                    <p className="font-medium">⚠ Move failed</p>
                    <p className="mt-0.5 text-red-200/70">{dragErrorMessage}</p>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
