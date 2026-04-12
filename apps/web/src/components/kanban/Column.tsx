// apps/web/src/components/kanban/Column.tsx
//
// Kanban column — uses @dnd-kit/react useSortable with type 'column'.
// Lower collision priority so cards dropping into columns take precedence.
//
// Styling directives (from Phase 3 spec):
// Columns should be subtle placeholders, not solid blocks:
// "flex flex-col gap-3 w-80 bg-[hsl(var(--surface-glass-border))] rounded-2xl p-3 border border-[hsl(var(--surface-glass-border))]"

import { forwardRef } from 'react';
import { useSortable } from '@dnd-kit/react/sortable';
import { CollisionPriority } from '@dnd-kit/abstract';
import { cn } from '@/lib/utils';
import { COLUMNS_DEF } from '@/types';
import { Card } from './Card';
import { EmptyState } from '../common/EmptyState';
import type { KanbanCard } from '@/lib/schema';

interface ColumnProps {
  columnId: string;
  index: number;
  cardIds: string[];
  cards: KanbanCard[];
  hoveredCardId: string | null;
  onHoverCard: (id: string | null) => void;
  onCardClick: (cardId: string) => void;
}

export const Column = forwardRef<HTMLDivElement, ColumnProps>(
  function Column({ columnId, index, cardIds, cards, hoveredCardId, onHoverCard, onCardClick }, ref) {
    const { ref: sortableRef, isDropTarget } = useSortable({
      id: columnId,
      index,
      type: 'column',
      accept: ['item', 'column'],
      collisionPriority: CollisionPriority.Low,
    });

    const colDef = COLUMNS_DEF[Number(columnId)];

    return (
      <div
        ref={(node) => {
          // Merge refs: useSortable ref + forwarded ref
          (sortableRef as (node: HTMLDivElement | null) => void)(node);
          if (typeof ref === 'function') ref(node);
          else if (ref) ref.current = node;
        }}
        className={cn(
          'flex flex-col gap-3 w-80 shrink-0 min-w-[260px] rounded-2xl p-3',
          'border transition-all duration-[var(--duration-default)] ease-[var(--ease-spring)]',
          'bg-[hsl(var(--surface-glass-border)/0.3)]',
          'border-[hsl(var(--surface-glass-border))]',
          isDropTarget && 'bg-[hsl(var(--brand-500)/0.05)] border-[hsl(var(--brand-500)/0.3)]',
        )}
      >
        {/* Column Header */}
        <div className="flex items-center justify-between px-1">
          <div>
            <h3 className={cn(
              'text-sm font-semibold tracking-tight',
              'text-[hsl(var(--neutral-100))]',
            )}>
              {colDef?.name ?? `Column ${columnId}`}
            </h3>
            <p className="text-[10px] font-medium tracking-wide uppercase text-[hsl(var(--neutral-400))] mt-0.5">
              {colDef?.description ?? ''}
            </p>
          </div>
          <span className={cn(
            'text-xs font-medium px-2 py-0.5 rounded-full',
            'bg-[hsl(var(--neutral-800))] text-[hsl(var(--neutral-400))]',
          )}>
            {cardIds.length}
          </span>
        </div>

        {/* Card List */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {cardIds.length === 0 ? (
            <EmptyState message="No cards" />
          ) : (
            cardIds.map((id, idx) => {
              const card = cards.find((c) => c.id === id);
              if (!card) return null;
              return (
                <Card
                  key={id}
                  card={card}
                  index={idx}
                  column={columnId}
                  isHoveredParent={hoveredCardId === card.id || (card.parent_id != null && hoveredCardId === card.parent_id)}
                  onClick={() => onCardClick(card.id)}
                  onMouseEnter={() => onHoverCard(card.id)}
                  onMouseLeave={() => onHoverCard(null)}
                />
              );
            })
          )}
        </div>
      </div>
    );
  },
);
