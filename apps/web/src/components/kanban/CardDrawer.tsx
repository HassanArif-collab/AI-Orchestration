import { useEffect, useRef } from 'react';
import type { KanbanCard } from '@/lib/schema';
import { useAgentStream } from '@/hooks/useAgentStream';
import { usePipelineState } from '@/hooks/usePipelineState';
import { AgentLog } from '../common/AgentLog';
import { StatusBadge } from '../common/StatusBadge';
import { ReviewPanel } from '../review/ReviewPanel';
import { ScriptViewer } from '../review/ScriptViewer';

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

interface Props {
  card: KanbanCard | null;
  onClose: () => void;
}

export function CardDrawer({ card, onClose }: Props) {
  const { thoughts, isConnected, connectionError, bottomRef, forceReconnect } = useAgentStream(card?.id ?? null);
  // Use pipeline_run_id for polling (NOT card.id — they are different values)
  const runId = card?.pipeline_run_id ?? null;
  const { state, isWaitingForReview } = usePipelineState(runId);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    if (!card) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [card, onClose]);

  if (!card) return null;

  const brief = getTopicBrief(card);
  const viabilityScore = getViabilityScore(card);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label="Card details"
        className="fixed right-0 top-0 h-full w-[600px] max-w-[90vw] bg-gray-900 border-l border-gray-700 z-50 flex flex-col shadow-2xl animate-slide-in"
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-800 shrink-0">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-bold text-white truncate">
                {brief?.title ?? card.title ?? 'Untitled'}
              </h2>
              <p className="text-sm text-gray-400 mt-1 line-clamp-2">
                {brief?.description ?? ''}
              </p>
            </div>
            <button onClick={onClose} className="text-gray-500 hover:text-white ml-2 text-xl">
              ✕
            </button>
          </div>

          {/* Status + Metrics bar */}
          <div className="flex items-center gap-4 mt-3">
            <StatusBadge status={card.status} />
            {state && (
              <>
                <span className="text-xs text-gray-500">
                  Score: <span className="text-white font-mono">{state.best_score}%</span>
                </span>
                <span className="text-xs text-gray-500">
                  Iteration: <span className="text-white font-mono">{state.iteration_count}/20</span>
                </span>
              </>
            )}
            {isConnected ? (
              <span className="text-xs text-green-400">● Live</span>
            ) : connectionError ? (
              <span className="flex items-center gap-1.5 text-xs text-yellow-400">
                <span className="animate-spin">⟳</span>
                <span>{connectionError}</span>
                {connectionError.includes('Click Retry') && (
                  <button
                    onClick={forceReconnect}
                    className="ml-1 text-xs text-blue-400 hover:text-blue-300 underline"
                  >
                    Retry
                  </button>
                )}
              </span>
            ) : (
              <span className="text-xs text-red-400">○ Disconnected</span>
            )}
          </div>
        </div>

        {/* Content Area — scrollable */}
        <div className="flex-1 overflow-y-auto scrollbar-thin">

          {/* Script + Visuals Viewer (only when visual_plan exists) */}
          {state?.visual_plan && (
            <div className="border-b border-gray-800">
              <ScriptViewer
                narration={state.current_draft}
                visuals={state.visual_plan}
              />
            </div>
          )}

          {/* Review Panel (only when waiting for human review) */}
          {isWaitingForReview && (
            <div className="border-b border-gray-800">
              <ReviewPanel
                cardId={card.id}
                cardTitle={brief?.title}
                cardScore={viabilityScore}
                cardIterationCount={state?.iteration_count}
                cardContent={state?.current_draft}
                cardVisualPlan={state?.visual_plan}
                onDecision={onClose}
              />
            </div>
          )}

          {/* Agent Activity Log */}
          <div className="p-4">
            <h3 className="text-sm font-semibold text-gray-400 mb-3">
              Agent Activity ({thoughts.length} events)
            </h3>
            <div className="space-y-1">
              {thoughts.map((t) => (
                <AgentLog key={t.id} thought={t} />
              ))}
              <div ref={bottomRef} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
