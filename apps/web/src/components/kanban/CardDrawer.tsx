// apps/web/src/components/kanban/CardDrawer.tsx
//
// Side drawer that opens when clicking a card.
// Uses Radix UI Dialog for proper a11y, Escape handling, focus management.
//
// Required Radix hierarchy: Dialog.Root → Dialog.Portal → Dialog.Overlay → Dialog.Content
// CRITICAL: Dialog.Portal is required — without it, fixed positioning breaks
// inside parent transforms/overflow.
// CRITICAL: Dialog.Close is required for Escape key + focus return to trigger element.
//
// Features:
// - Pipeline state polling (usePipelineStateForCard)
// - Live agent thoughts streaming (useAgentStream via Supabase Realtime)
// - Soft delete button with undo toast
// - Connection drop indicator with manual retry
// - Glassmorphism styling throughout

import * as Dialog from '@radix-ui/react-dialog';
import { X, Trash2, Wifi, WifiOff } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/lib/store';
import { useAgentStream } from '@/hooks/useAgentStream';
import { usePipelineStateForCard } from '@/hooks/usePipelineState';
import { deleteCard as deleteCardApi } from '@/lib/api';
import { AgentLog } from '../common/AgentLog';
import { StatusBadge } from '../common/StatusBadge';
import { showToast } from '@/hooks/useToast';
import { mapApiError } from '@/lib/errorMapper';
import type { KanbanCard } from '@/lib/schema';

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

export function CardDrawer() {
  const activeDrawerCardId = useAppStore((s) => s.activeDrawerCardId);
  const setActiveDrawerCardId = useAppStore((s) => s.setActiveDrawerCardId);
  const cards = useAppStore((s) => s.cards);
  const card = cards?.find((c) => c.id === activeDrawerCardId) ?? null;

  const brief = getTopicBrief(card ?? undefined as unknown as KanbanCard);
  const viabilityScore = card ? getViabilityScore(card) : null;

  // Pipeline state polling (conditional — only for col 4/5)
  const { state } =
    usePipelineStateForCard(card);

  // Agent thoughts streaming
  const { thoughts, isConnected, connectionError, bottomRef, forceReconnect } =
    useAgentStream(activeDrawerCardId);

  const handleSoftDelete = async () => {
    if (!activeDrawerCardId) return;
    try {
      await deleteCardApi(activeDrawerCardId);
      setActiveDrawerCardId(null);
      showToast({ type: 'info', title: 'Card deleted', message: 'The card has been soft-deleted.' });
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({ type: 'error', title: 'Delete failed', message: friendlyError.message });
    }
  };

  return (
    <Dialog.Root
      open={activeDrawerCardId !== null}
      onOpenChange={(open) => !open && setActiveDrawerCardId(null)}
    >
      <Dialog.Portal>
        {/* Backdrop */}
        <Dialog.Overlay
          className={cn(
            'fixed inset-0 bg-black/40 backdrop-blur-sm',
            'z-[var(--z-drawer-overlay)]',
            'transition-opacity duration-[var(--duration-default)]',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0',
          )}
        />

        {/* Drawer panel */}
        <Dialog.Content
          className={cn(
            'fixed right-0 top-0 h-full',
            'w-[600px] max-w-[calc(100vw-20rem)]',
            'bg-[hsl(var(--surface-sunken)/0.85)] backdrop-blur-3xl',
            'border-l border-[hsl(var(--surface-glass-border))]',
            'z-[var(--z-drawer)]',
            'shadow-2xl',
            'flex flex-col',
            'transition-transform duration-[var(--duration-default)] ease-[var(--ease-drawer)]',
            'data-[state=open]:animate-in data-[state=open]:slide-in-from-right',
            'data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right',
            'focus:outline-none',
          )}
        >
          {card && (
            <>
              {/* Header */}
              <div className="p-5 border-b border-[hsl(var(--surface-glass-border))] shrink-0">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h2 className="text-lg font-semibold tracking-tight text-[hsl(var(--neutral-100))] truncate">
                      {brief?.title ?? card.title ?? 'Untitled'}
                    </h2>
                    {brief?.description && (
                      <p className="text-sm text-[hsl(var(--neutral-400))] mt-1 line-clamp-2">
                        {brief.description}
                      </p>
                    )}
                  </div>
                  <Dialog.Close asChild>
                    <button
                      className={cn(
                        'ml-3 p-1.5 rounded-lg',
                        'text-[hsl(var(--neutral-400))] hover:text-[hsl(var(--neutral-100))]',
                        'hover:bg-[hsl(var(--neutral-800))]',
                        'transition-colors duration-[var(--duration-default)]',
                        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
                      )}
                      aria-label="Close drawer"
                    >
                      <X className="w-4 h-4" strokeWidth={1.5} />
                    </button>
                  </Dialog.Close>
                </div>

                {/* Status + Metrics bar */}
                <div className="flex items-center gap-4 mt-3 flex-wrap">
                  <StatusBadge status={card.status} />

                  {viabilityScore != null && (
                    <span className="text-xs text-[hsl(var(--neutral-400))]">
                      Score:{' '}
                      <span className="text-[hsl(var(--neutral-100))] font-mono">
                        {viabilityScore}%
                      </span>
                    </span>
                  )}

                  {state && (
                    <>
                      <span className="text-xs text-[hsl(var(--neutral-400))]">
                        Score:{' '}
                        <span className="text-[hsl(var(--neutral-100))] font-mono">
                          {state.best_score}%
                        </span>
                      </span>
                      <span className="text-xs text-[hsl(var(--neutral-400))]">
                        Iteration:{' '}
                        <span className="text-[hsl(var(--neutral-100))] font-mono">
                          {state.iteration_count}/20
                        </span>
                      </span>
                    </>
                  )}

                  {/* Connection indicator */}
                  {isConnected ? (
                    <span className="flex items-center gap-1.5 text-xs text-emerald-400">
                      <Wifi className="w-3 h-3" strokeWidth={1.5} />
                      Live
                    </span>
                  ) : connectionError ? (
                    <span className="flex items-center gap-1.5 text-xs text-amber-400">
                      <WifiOff className="w-3 h-3" strokeWidth={1.5} />
                      <span className="text-amber-400 text-xs">{connectionError}</span>
                      {connectionError.includes('Retry') && (
                        <button
                          onClick={forceReconnect}
                          className="ml-1 text-xs text-[hsl(var(--brand-300))] hover:text-[hsl(var(--brand-500))] underline"
                        >
                          Retry
                        </button>
                      )}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-xs text-red-400">
                      <WifiOff className="w-3 h-3" strokeWidth={1.5} />
                      Disconnected
                    </span>
                  )}
                </div>

                {/* Pipeline progress bar */}
                {state && (
                  <div className="mt-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-medium tracking-wide uppercase text-[hsl(var(--neutral-400))]">
                        Pipeline Status
                      </span>
                      <span className="text-[10px] font-mono text-[hsl(var(--brand-300))]">
                        {state.pipeline_status}
                      </span>
                    </div>
                    <div className="w-full bg-[hsl(var(--neutral-800))] rounded-full h-1.5">
                      <div
                        className="h-1.5 rounded-full bg-[hsl(var(--brand-500))] transition-all duration-500"
                        style={{ width: `${Math.min(100, (state.iteration_count / 20) * 100)}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Scrollable content area */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {/* Current Draft (when available) */}
                {state?.current_draft && (
                  <section>
                    <h3 className="text-[10px] font-medium tracking-wide uppercase text-[hsl(var(--neutral-400))] mb-2">
                      Current Draft
                    </h3>
                    <pre
                      className={cn(
                        'text-sm text-[hsl(var(--neutral-100))] font-mono leading-relaxed',
                        'bg-[hsl(var(--neutral-800)/0.5)] rounded-xl p-4',
                        'border border-[hsl(var(--surface-glass-border))]',
                        'whitespace-pre-wrap max-h-64 overflow-y-auto',
                      )}
                    >
                      {state.current_draft}
                    </pre>
                  </section>
                )}

                {/* Visual Plan (when available) */}
                {state?.visual_plan && (
                  <section>
                    <h3 className="text-[10px] font-medium tracking-wide uppercase text-[hsl(var(--neutral-400))] mb-2">
                      Visual Plan
                    </h3>
                    <pre
                      className={cn(
                        'text-sm text-[hsl(var(--lineage-cyan))] font-mono leading-relaxed',
                        'bg-[hsl(var(--neutral-800)/0.5)] rounded-xl p-4',
                        'border border-[hsl(var(--surface-glass-border))]',
                        'whitespace-pre-wrap max-h-48 overflow-y-auto',
                      )}
                    >
                      {state.visual_plan}
                    </pre>
                  </section>
                )}

                {/* Pipeline Error */}
                {state?.error && (
                  <div
                    className={cn(
                      'rounded-xl p-4 border border-red-500/30',
                      'bg-red-500/10 text-red-300',
                    )}
                  >
                    <p className="text-xs font-semibold mb-1">Pipeline Error</p>
                    <p className="text-xs">{state.error}</p>
                  </div>
                )}

                {/* Agent Activity Log */}
                <section>
                  <h3 className="text-[10px] font-medium tracking-wide uppercase text-[hsl(var(--neutral-400))] mb-3">
                    Agent Activity ({thoughts.length} events)
                  </h3>
                  <div className="space-y-1">
                    {thoughts.map((t) => (
                      <AgentLog key={t.id} thought={t} />
                    ))}
                    <div ref={bottomRef} />
                  </div>
                </section>
              </div>

              {/* Footer with actions */}
              <div className="p-4 border-t border-[hsl(var(--surface-glass-border))] shrink-0">
                <button
                  onClick={handleSoftDelete}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium',
                    'text-red-400 bg-red-500/10 hover:bg-red-500/20',
                    'transition-colors duration-[var(--duration-default)]',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400',
                  )}
                >
                  <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                  Soft Delete
                </button>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
