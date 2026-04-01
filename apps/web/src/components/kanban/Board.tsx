import { useState, useCallback, useEffect, useRef } from 'react';
import { DndContext, closestCenter, DragOverlay } from '@dnd-kit/core';
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core';
import { Column } from './Column';
import { CardDrawer } from './CardDrawer';
import { useCards, groupByColumn } from '../../hooks/useCards';
import { api } from '../../lib/api';
import { COLUMNS } from '../../types';
import type { KanbanCard } from '../../types';
import { showToast } from '../../hooks/useToast';
import { mapApiError } from '../../lib/errorMapper';

// ── Pipeline transition rules ──
// Based on the actual column layout:
//   1: Topic Finding → 2: Suggested Topics → 3: Researching →
//   4: Script Evolution → 5: Review + Visuals → 6: Published
const VALID_TRANSITIONS: Record<number, number[]> = {
  1: [2],      // Topic Finding → Suggested Topics
  2: [3],      // Suggested Topics → Researching (start pipeline)
  3: [4],      // Researching → Script Evolution
  4: [5],      // Script Evolution → Review + Visuals
  5: [6],      // Review + Visuals → Published
  6: [],       // Published — terminal state
};

function isValidTransition(fromCol: number, toCol: number): boolean {
  return (VALID_TRANSITIONS[fromCol] ?? []).includes(toCol);
}

function getTransitionErrorMessage(fromCol: number, toCol: number): string {
  const fromName = COLUMNS[fromCol]?.name ?? `Column ${fromCol}`;
  const toName = COLUMNS[toCol]?.name ?? `Column ${toCol}`;
  const validTargets = VALID_TRANSITIONS[fromCol] ?? [];

  if (validTargets.length === 0) {
    return `"${fromName}" is a terminal state. Cards cannot be moved from here.`;
  }

  if (toCol < fromCol) {
    return `Cannot move cards backward from "${fromName}" to "${toName}". Use the card action buttons instead.`;
  }

  const validNames = validTargets
    .map((c) => COLUMNS[c]?.name ?? `Column ${c}`)
    .join(', ');
  return `Cards in "${fromName}" can only move to: ${validNames}. Use the action buttons on the card instead.`;
}

// ── Column helpers ──

function getColumnName(colNum: number): string {
  return COLUMNS[colNum]?.name ?? `Column ${colNum}`;
}

// ── Drag Overlay Component ──
function CardOverlay({ card }: { card: KanbanCard }) {
  return (
    <div className="bg-gray-800 rounded-lg p-3 shadow-2xl border border-blue-500 w-[260px] rotate-2">
      <h4 className="text-sm font-medium text-white truncate">{card.topic_brief?.title ?? 'Untitled Topic'}</h4>
      <p className="text-xs text-gray-400 mt-1 line-clamp-2">{card.topic_brief?.description ?? ''}</p>
    </div>
  );
}

export function Board() {
  const { cards, isLoading, error, mutate } = useCards();
  const [selectedCard, setSelectedCard] = useState<KanbanCard | null>(null);
  const [optimisticMoves, setOptimisticMoves] = useState<Record<string, number>>({});
  const [dragError, setDragError] = useState<{ cardId: string; message: string } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const pendingTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Clean up pending timers on unmount to prevent stale state updates
  useEffect(() => {
    return () => {
      pendingTimersRef.current.forEach(clearTimeout);
      pendingTimersRef.current = [];
    };
  }, []);

  /** Schedule a timer that is cleaned up on unmount */
  const scheduleTimer = useCallback((fn: () => void, delay: number) => {
    const id = setTimeout(fn, delay);
    pendingTimersRef.current.push(id);
    return id;
  }, []);

  // Compute effective card groupings (optimistic moves override real columns)
  const getEffectiveColumn = useCallback(
    (card: KanbanCard) => optimisticMoves[card.id] ?? card.column,
    [optimisticMoves],
  );

  const grouped = groupByColumn(
    cards.map((card) => ({
      ...card,
      column: getEffectiveColumn(card),
    })),
  );

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      setActiveId(event.active.id as string);
      setIsDragging(true);
    },
    [],
  );

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      const { active, over } = event;
      setIsDragging(false);
      setActiveId(null);

      if (!over) return;

      const cardId = active.id as string;
      const targetColumn = (over.data?.current as { columnNumber?: number })?.columnNumber;

      if (targetColumn == null) return;

      const card = cards.find((c) => c.id === cardId);
      if (!card) return;

      // Same column — ignore
      if (card.column === targetColumn) return;

      // ── Validate transition (Issue 7) ──
      if (!isValidTransition(card.column, targetColumn)) {
        const errorMsg = getTransitionErrorMessage(card.column, targetColumn);

        showToast({
          type: 'error',
          title: 'Invalid move',
          message: errorMsg,
        });

        // Brief visual shake indicator
        setDragError({ cardId, message: errorMsg });
        scheduleTimer(() => setDragError(null), 3000);

        return;
      }

      // ── Optimistic update (Issue 2) ──
      setOptimisticMoves((prev) => ({ ...prev, [cardId]: targetColumn }));

      try {
        // Make API call
        await api.moveCard(cardId, targetColumn);

        // Success: refetch to get authoritative state, clear optimistic
        setOptimisticMoves((prev) => {
          const next = { ...prev };
          delete next[cardId];
          return next;
        });

        showToast({
          type: 'success',
          title: 'Card moved',
          message: `Moved to ${getColumnName(targetColumn)}`,
        });

        // Refetch cards so local state matches backend
        mutate?.();
      } catch (err) {
        // Failure: show error, revert after 3 seconds
        const friendlyError = mapApiError(err);

        setDragError({ cardId, message: friendlyError.message });

        showToast({
          type: 'error',
          title: 'Could not move card',
          message: friendlyError.message,
        });

        // Revert optimistic move after 3 seconds
        scheduleTimer(() => {
          setOptimisticMoves((prev) => {
            const next = { ...prev };
            delete next[cardId];
            return next;
          });
          setDragError(null);
        }, 3000);
      }
    },
    [cards, mutate],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        Loading pipeline...
      </div>
    );
  }

  if (error) {
    const friendlyError = mapApiError(error);
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <p className="text-red-400 text-sm font-medium mb-2">{friendlyError.title}</p>
          <p className="text-red-300/70 text-xs mb-4">{friendlyError.message}</p>
          <button
            onClick={() => mutate?.()}
            className="bg-red-700 hover:bg-red-600 text-white px-4 py-2 rounded text-sm font-medium transition-colors"
          >
            {friendlyError.action ?? 'Retry'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <DndContext
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="flex gap-4 overflow-x-auto p-4 h-full relative">
          {[1, 2, 3, 4, 5, 6].map((colNum) => (
            <Column
              key={colNum}
              columnNumber={colNum}
              definition={COLUMNS[colNum]}
              cards={grouped[colNum] ?? []}
              onCardClick={setSelectedCard}
              isDragging={isDragging}
              dragErrorCardId={dragError?.cardId ?? null}
              dragErrorMessage={dragError?.message ?? null}
            />
          ))}

          {/* Drag in-progress overlay */}
          {isDragging && (
            <div className="fixed inset-0 pointer-events-none z-50">
              <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-blue-900/90 border border-blue-500 rounded-lg px-4 py-2 text-white text-sm animate-fade-in">
                Moving card...
              </div>
            </div>
          )}

          {/* Invalid drag error overlay */}
          {dragError && (
            <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 animate-shake">
              <div className="bg-red-900/90 border border-red-500 rounded-lg px-4 py-2 text-white text-sm max-w-sm">
                <p className="font-medium flex items-center gap-2">
                  <span>⚠</span>
                  <span>{dragError.message}</span>
                </p>
              </div>
            </div>
          )}
        </div>

        <DragOverlay>
          {activeId ? <CardOverlay card={cards.find((c) => c.id === activeId)!} /> : null}
        </DragOverlay>
      </DndContext>

      {/* Slide-out drawer for card details */}
      <CardDrawer
        card={selectedCard}
        onClose={() => setSelectedCard(null)}
      />
    </>
  );
}
