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
//
// CRITICAL: The `isSortable` type guard is REQUIRED before accessing
// source.initialGroup, source.group, source.initialIndex, source.index.
// Without it, TypeScript marks these as `unknown`, forcing `any` casts.

import { useRef } from 'react';
import { DragDropProvider } from '@dnd-kit/react';
import { isSortable } from '@dnd-kit/react/sortable';
import { move } from '@dnd-kit/helpers';
import { cn } from '@/lib/utils';
import { useCards, COLUMNS, type ColumnKey } from '@/hooks/useCards';
import { useAppStore } from '@/lib/store';
import { moveCard as moveCardApi, startProduction } from '@/lib/api';
import { showToast } from '@/hooks/useToast';
import { mapApiError } from '@/lib/errorMapper';
import { Column } from './Column';

export function Board() {
  const { cards, items, setItems, isLoading, error, mutate } = useCards();
  const snapshot = useRef<Record<ColumnKey, string[]>>({
    '1': [], '2': [], '3': [], '4': [], '5': [], '6': [],
  });

  // Lineage hover state — parent_id glow effect
  const hoveredCardId = useAppStore((s) => s.hoveredCardId);
  const setHoveredCardId = useAppStore((s) => s.setHoveredCardId);

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

  return (
    <DragDropProvider
      onDragStart={() => {
        snapshot.current = structuredClone(items); // save pre-drag state for cancel restore
      }}
      onDragOver={(event) => {
        const { source } = event.operation;
        if (source?.type === 'column') return; // skip column drags, only move cards
        setItems((prev) => move(prev, event) as Record<ColumnKey, string[]>);
      }}
      onDragEnd={async (event) => {
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
          }
        }

        // Revalidate to sync with ground truth from DB
        mutate?.();
      }}
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
    </DragDropProvider>
  );
}
