import type { KanbanCard, ColumnDef } from '../../types';
import { Card } from './Card';
import { EmptyState } from '../common/EmptyState';
import { useDroppable } from '@dnd-kit/core';

interface Props {
  columnNumber: number;
  definition: ColumnDef;
  cards: KanbanCard[];
  onCardClick: (card: KanbanCard) => void;
}

export function Column({ columnNumber, definition, cards, onCardClick }: Props) {
  // Make this column a valid drop target for drag-and-drop
  const { setNodeRef, isOver } = useDroppable({
    id: `column-${columnNumber}`,
    data: { columnNumber },
  });

  return (
    <div
      ref={setNodeRef}
      className={`
        flex flex-col w-kanban-col min-w-[260px] shrink-0
        bg-gray-900 rounded-xl border
        ${isOver ? 'border-blue-500 bg-gray-800/50' : 'border-gray-800'}
        transition-colors duration-200
      `}
    >
      {/* Column Header */}
      <div className="p-3 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">
            {definition.name}
          </h3>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
            {cards.length}
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
            <Card
              key={card.id}
              card={card}
              onClick={() => onCardClick(card)}
            />
          ))
        )}
      </div>
    </div>
  );
}
