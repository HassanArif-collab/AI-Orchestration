import { useState, useCallback } from 'react';
import { DndContext, closestCenter } from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import { Column } from './Column';
import { CardDrawer } from './CardDrawer';
import { useCards, groupByColumn } from '../../hooks/useCards';
import { api } from '../../lib/api';
import { COLUMNS } from '../../types';
import type { KanbanCard } from '../../types';

export function Board() {
  const { cards, isLoading, error } = useCards();
  const [selectedCard, setSelectedCard] = useState<KanbanCard | null>(null);
  const grouped = groupByColumn(cards);

  const handleDragEnd = useCallback(async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;

    const cardId = active.id as string;
    const targetColumn = (over.data?.current as { columnNumber?: number })?.columnNumber;

    if (targetColumn == null) return;

    // Only allow specific transitions
    // Column 2 → 3 (approve topic → start research)
    // Other moves can be restricted based on business rules
    try {
      await api.moveCard(cardId, targetColumn);
    } catch (err) {
      console.error('Failed to move card:', err);
    }
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        Loading pipeline...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        Failed to load cards: {String(error)}
      </div>
    );
  }

  return (
    <>
      <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <div className="flex gap-4 overflow-x-auto p-4 h-full">
          {[1, 2, 3, 4, 5, 6].map((colNum) => (
            <Column
              key={colNum}
              columnNumber={colNum}
              definition={COLUMNS[colNum]}
              cards={grouped[colNum]}
              onCardClick={setSelectedCard}
            />
          ))}
        </div>
      </DndContext>

      {/* Slide-out drawer for card details */}
      <CardDrawer
        card={selectedCard}
        onClose={() => setSelectedCard(null)}
      />
    </>
  );
}
