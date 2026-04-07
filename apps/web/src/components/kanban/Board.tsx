// apps/web/src/components/kanban/Board.tsx
//
// Core Kanban board using @dnd-kit/react (latest v1.0 protocol).
// Uses DragDropProvider (NOT the deprecated DndContext).
//
// Architecture:
// - Items (Record<string, string[]>) come from useCards hook (derived from SWR)
// - DragDropProvider handles optimistic UI via move() from @dnd-kit/helpers
// - onDragEnd triggers the exact backend API based on target column
// - Cancel snapshot enables drag undo via structuredClone
// - DragOverlay renders a polished drag preview above the board
//
// CRITICAL: The `isSortable` type guard is REQUIRED before accessing
// source.initialGroup, source.group, source.initialIndex, source.index.
// Without it, TypeScript marks these as `unknown`, forcing `any` casts.

import { useRef, useState } from 'react';
import { DragDropProvider, type DragEndEvent, type DragOverEvent, type DragStartEvent } from '@dnd-kit/react';
import { isSortable } from '@dnd-kit/react/sortable';
import { move } from '@dnd-kit/helpers';
import { cn } from '@/lib/utils';
import { useCards, COLUMNS, type ColumnKey } from '@/hooks/useCards';
import { useAppStore } from '@/lib/store';
import { moveCard as moveCardApi, startProduction } from '@/lib/api';
import { showToast } from '@/hooks/useToast';
import { mapApiError } from '@/lib/errorMapper';
import { Column } from './Column';
import type { KanbanCard } from '@/lib/schema';

/** Polished drag overlay shown above the board while dragging a card. */
function DragOverlayCard({ card }: { card: KanbanCard | null }) {
  if (!card) return null;

  const meta = card.metadata as Record<string, unknown> | undefined;
  const brief = meta?.topic_brief as Record<string, unknown> | undefined;
  const title = typeof brief?.title === 'string' ? brief.title : card.title ?? 'Untitled Topic';

  return (
    <div
      className={cn(
        'relative group p-4 rounded-xl',
        'backdrop-blur-xl',
        'bg-[hsl(var(--surface-glass))]',
        'border border-[hsl(var(--brand-500)/0.4)]',
        'shadow-[var(--shadow-glow)]',
        'opacity-90 rotate-2 scale-105',
        'pointer-events-none',
        'w-72',
      )}
    >
      <h4 className="text-sm font-medium text-[hsl(var(--neutral-100))] truncate">
        {title}
      </h4>
      <p className="text-xs text-[hsl(var(--neutral-400))] mt-1">
        Dragging to new column...
      </p>
    </div>
  );
}

export function Board() {
  const { cards, items, setItems, isLoading, error, mutate } = useCards();
  const snapshot = useRef<Record<ColumnKey, string[]>>({
    '1': [], '2': [], '3': [], '4': [], '5': [], '6': [],
  });
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Lineage hover state — parent_id glow effect
  const hoveredCardId = useAppStore((s) => s.hoveredCardId);
  const setHoveredCardId = useAppStore((s) => s.setHoveredCardId);

  // Drag overlay state
  const [draggingCard, setDraggingCard] = useState<KanbanCard | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full text-[hsl(var(--neutral-400))] text-sm">
        Loading pipeline...
      </div>
    );
  }

  if (error) {
    const friendlyError = mapApiError(error);
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center max-w-md">
          <p className="text-red-400 text-sm font-semibold mb-2">{friendlyError.title}</p>
          <p className="text-red-300/70 text-xs mb-4">{friendlyError.message}</p>
          <button
            onClick={() => mutate?.()}
            className="rounded-lg bg-red-500/20 text-red-300 px-4 py-2 text-sm font-medium hover:bg-red-500/30 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
          >
            {friendlyError.action ?? 'Retry'}
          </button>
        </div>
      </div>
    );
  }

  const handleDragStart = (event: DragStartEvent) => {
    snapshot.current = structuredClone(items); // save pre-drag state for cancel restore
    const { source } = event.operation;
    if (source?.type === 'item') {
      const card = cards.find((c) => c.id === source.id);
      setDraggingCard(card ?? null);
    }
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { source } = event.operation;
    if (source?.type === 'column') return; // skip column drags, only move cards
    setItems((prev) => move(prev, event) as Record<ColumnKey, string[]>);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    setDraggingCard(null);

    if (event.canceled) {
      setItems(snapshot.current); // restore to pre-drag state
      return;
    }

    const { source, target } = event.operation;
    if (!isSortable(source) || !target) return;

    const cardId = source.id as string;
    const targetColumn = target.id as string;

    // Moving to Column 4 triggers production pipeline
    if (targetColumn === '4') {
      try {
        await startProduction(cardId);
        showToast({
          type: 'success',
          title: 'Production started',
          message: 'LangGraph pipeline is now running.',
        });
      } catch (err) {
        const friendlyError = mapApiError(err);
        showToast({ type: 'error', title: friendlyError.title, message: friendlyError.message });
        // Optimistic revert after 3 seconds
        const timer = setTimeout(() => {
          setItems(snapshot.current);
        }, 3000);
        timersRef.current.push(timer);
      }
    } else {
      // General move — PATCH with stage + position
      try {
        await moveCardApi(cardId, {
          stage: Number(targetColumn),
          position: source.index,
        });
        showToast({
          type: 'success',
          title: 'Card moved',
          message: `Moved to Column ${targetColumn}`,
        });
      } catch (err) {
        const friendlyError = mapApiError(err);
        showToast({ type: 'error', title: 'Move failed', message: friendlyError.message });
        // Optimistic revert after 3 seconds
        const timer = setTimeout(() => {
          setItems(snapshot.current);
        }, 3000);
        timersRef.current.push(timer);
      }
    }

    // Revalidate to sync with ground truth from DB
    mutate?.();
  };

  return (
    <DragDropProvider
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
    >
      <div
        className={cn(
          'flex-1 overflow-x-auto p-4',
          'flex gap-4 h-full',
          'relative z-[var(--z-base)]',
        )}
      >
        {COLUMNS.map((colId, colIndex) => (
          <Column
            key={colId}
            columnId={colId}
            index={colIndex}
            cardIds={items[colId] ?? []}
            cards={cards}
            hoveredCardId={hoveredCardId}
            onHoverCard={setHoveredCardId}
            onCardClick={(cardId) =>
              useAppStore.getState().setActiveDrawerCardId(cardId)
            }
          />
        ))}
      </div>

      {/* Drag Overlay — renders above the board at z-drag-overlay */}
      <DragOverlayCard card={draggingCard} />
    </DragDropProvider>
  );
}
