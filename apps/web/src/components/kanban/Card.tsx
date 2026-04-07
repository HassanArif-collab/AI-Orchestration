// apps/web/src/components/kanban/Card.tsx
//
// Draggable Kanban card — uses @dnd-kit/react useSortable with type 'item'.
//
// Styling directives (from Phase 3 spec):
// Base: "relative group p-4 rounded-xl backdrop-blur-xl bg-[hsl(var(--surface-glass))]
//  border border-[hsl(var(--surface-glass-border))] hover:shadow-[var(--shadow-glow)]
//  transition-all duration-[var(--duration-default)] ease-[var(--ease-spring)]
//  cursor-grab active:cursor-grabbing"
// Processing: "animate-pulse shadow-[var(--shadow-glow)] border-[hsl(var(--brand-500)/0.5)]"
//
// Lineage: Hovering a parent card applies ring glow to any card where
// card.parent_id === hoverCard.id.
//
// Column-specific actions:
// - Col 1: Read-only, progress pulse
// - Col 2: Save Topic button (POST /api/kanban/cards/{id}/save)
// - Col 3: Extend expiry (POST /api/kanban/tasks/{id}/extend)
// - Col 4: Active LangGraph — processing indicator
// - Col 5: Human review — opens drawer
// - Col 6: Published — read-only, published badge

import { useState } from 'react';
import { useSortable } from '@dnd-kit/react/sortable';
import {
  Save,
  Rocket,
  RotateCcw,
  Loader2,
  Timer,
  CheckCircle2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { KanbanCard } from '@/lib/schema';
import { StatusBadge } from '../common/StatusBadge';
import { useCardTimer } from '@/hooks/useCardTimer';
import { saveCard, startProduction, extendTaskExpiry } from '@/lib/api';
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

interface CardProps {
  card: KanbanCard;
  index: number;
  column: string;
  isHoveredParent?: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

export function Card({ card, index, column, isHoveredParent, onClick, onMouseEnter, onMouseLeave }: CardProps) {
  const timer = useCardTimer(card.column_index === 2 ? (card.expires_at ?? null) : null);
  const actionInfo = getCardAction(card);
  const [actionLoading, setActionLoading] = useState(false);
  const brief = getTopicBrief(card);
  const viabilityScore = getViabilityScore(card);

  const { ref, isDragging } = useSortable({
    id: card.id,
    index,
    type: 'item',
    accept: 'item',
    group: column,
  });

  const handleAction = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      switch (actionInfo.action) {
        case 'save':
          await saveCard(card.id);
          showToast({ type: 'success', title: 'Topic saved', message: 'The topic will not expire.' });
          break;
        case 'start_pipeline':
          await startProduction(card.id);
          showToast({ type: 'success', title: 'Pipeline started', message: 'Production is now running.' });
          break;
        case 'resubmit':
          await startProduction(card.id);
          showToast({ type: 'success', title: 'Resubmitted', message: 'Sent back to production.' });
          break;
        case 'review':
          onClick();
          break;
      }
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({ type: 'error', title: friendlyError.title, message: friendlyError.message });
    } finally {
      setActionLoading(false);
    }
  };

  const handleExtend = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(true);
    try {
      await extendTaskExpiry(card.id);
      showToast({ type: 'success', title: 'Extended', message: 'Expiry extended by 3 hours.' });
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({ type: 'error', title: 'Extend failed', message: friendlyError.message });
    } finally {
      setActionLoading(false);
    }
  };

  const isPublished = card.column_index === 6;
  const isProcessing = card.status === 'processing';

  return (
    <div
      ref={ref}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      data-dragging={isDragging}
      className={cn(
        'relative group p-4 rounded-xl mb-2',
        'backdrop-blur-xl',
        'bg-[hsl(var(--surface-glass))]',
        'border border-[hsl(var(--surface-glass-border))]',
        'shadow-[var(--shadow-glass)]',
        'hover:shadow-[var(--shadow-glow)]',
        'transition-all duration-[var(--duration-default)] ease-[var(--ease-spring)]',
        'cursor-grab active:cursor-grabbing',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
        // Processing glow
        isProcessing && 'animate-pulse shadow-[var(--shadow-glow)] border-[hsl(var(--brand-500)/0.5)]',
        // Error border
        card.status === 'error' && 'border-red-500/50',
        // Expired
        timer.isExpired && 'opacity-60',
        // Timer urgency border
        !timer.isExpired && timer.isCritical && 'border-amber-500/60',
        !timer.isExpired && timer.isWarning && 'border-yellow-600/40',
        // Dragging state
        isDragging && 'opacity-50 scale-95 ring-2 ring-[hsl(var(--brand-500)/0.5)]',
        // Lineage glow — parent or child highlighted
        isHoveredParent && 'ring-2 ring-purple-500/60 shadow-purple-500/20',
      )}
      tabIndex={0}
      role="button"
      aria-label={`Card: ${brief?.title ?? card.title}`}
    >
      {/* Title */}
      <h4 className="text-sm font-medium text-[hsl(var(--neutral-100))] truncate">
        {brief?.title ?? card.title ?? 'Untitled Topic'}
      </h4>

      {/* Description preview */}
      {brief?.description && (
        <p className="text-xs text-[hsl(var(--neutral-400))] mt-1 line-clamp-2">
          {brief.description}
        </p>
      )}

      {/* Status + Score row */}
      <div className="flex items-center justify-between mt-2">
        <StatusBadge status={card.status} />
        {viabilityScore != null && (
          <span className="text-xs text-[hsl(var(--neutral-400))] font-mono">
            {viabilityScore}%
          </span>
        )}
      </div>

      {/* Published badge */}
      {isPublished && (
        <div className="flex items-center gap-1.5 mt-2 text-emerald-400 text-xs font-medium">
          <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span>Published</span>
        </div>
      )}

      {/* Column 2: Timer countdown */}
      {card.column_index === 2 && card.expires_at && (
        <div className="mt-2 space-y-1.5">
          <div className="w-full bg-[hsl(var(--neutral-800))] rounded-full h-1">
            <div
              className={cn(
                'h-1 rounded-full transition-all duration-1000',
                timer.isCritical ? 'bg-amber-500' : timer.isWarning ? 'bg-yellow-500' : 'bg-emerald-500',
              )}
              style={{ width: `${100 - timer.percentage}%` }}
            />
          </div>
          <div className="flex items-center gap-1.5">
            <Timer className={cn(
              'w-3 h-3',
              timer.isExpired ? 'text-red-400' : timer.isCritical ? 'text-amber-400' : 'text-[hsl(var(--neutral-400))]',
            )} strokeWidth={1.5} />
            <span className={cn(
              'text-xs font-medium',
              timer.isExpired && 'text-red-400',
              timer.isCritical && !timer.isExpired && 'text-amber-400 animate-pulse',
              timer.isWarning && !timer.isCritical && !timer.isExpired && 'text-yellow-400',
              !timer.isWarning && !timer.isCritical && !timer.isExpired && 'text-[hsl(var(--neutral-400))]',
            )}>
              {timer.isExpired ? 'Expired' : `${timer.timeString} left`}
            </span>
            {!timer.isExpired && (
              <button
                onClick={handleExtend}
                disabled={actionLoading}
                className="ml-auto text-[10px] text-[hsl(var(--neutral-400))] hover:text-[hsl(var(--neutral-100))] transition-colors focus-visible:outline-none"
                aria-label="Extend expiry by 3 hours"
              >
                +3h
              </button>
            )}
          </div>
        </div>
      )}

      {/* Action button */}
      {actionInfo.action !== 'none' && (
        <div className="mt-2">
          <p className={cn(
            'text-[10px] font-medium tracking-wide uppercase mb-1.5',
            actionInfo.variant === 'success' && 'text-emerald-400',
            actionInfo.variant === 'warning' && 'text-amber-400',
            actionInfo.variant === 'primary' && 'text-[hsl(var(--brand-300))]',
            actionInfo.variant === 'secondary' && 'text-[hsl(var(--neutral-400))]',
          )}>
            {actionInfo.reason}
          </p>
          <button
            onClick={handleAction}
            disabled={actionLoading}
            className={cn(
              'w-full flex items-center justify-center gap-1.5',
              'text-xs py-1.5 rounded-lg font-medium',
              'transition-all duration-[var(--duration-default)] ease-[var(--ease-spring)]',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
              actionInfo.variant === 'success' && 'bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30',
              actionInfo.variant === 'warning' && 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30',
              actionInfo.variant === 'primary' && 'bg-[hsl(var(--brand-500)/0.2)] text-[hsl(var(--brand-300))] hover:bg-[hsl(var(--brand-500)/0.3)]',
              actionInfo.variant === 'secondary' && 'bg-[hsl(var(--neutral-800))] text-[hsl(var(--neutral-100))] hover:bg-[hsl(var(--neutral-700))]',
            )}
          >
            {actionLoading ? (
              <Loader2 className="w-3 h-3 animate-spin" strokeWidth={1.5} />
            ) : (
              <>
                {actionInfo.action === 'save' && <Save className="w-3 h-3" strokeWidth={1.5} />}
                {actionInfo.action === 'start_pipeline' && <Rocket className="w-3 h-3" strokeWidth={1.5} />}
                {actionInfo.action === 'resubmit' && <RotateCcw className="w-3 h-3" strokeWidth={1.5} />}
                <span>{actionInfo.label}</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Non-actionable state message */}
      {actionInfo.action === 'none' && actionInfo.reason && !isPublished && (
        <p className="text-xs text-[hsl(var(--neutral-400))] mt-2 italic">
          {actionInfo.reason}
        </p>
      )}
    </div>
  );
}
