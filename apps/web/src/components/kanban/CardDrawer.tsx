import { useEffect, useRef } from 'react';
import type { KanbanCard } from '../../types';
import { useAgentStream } from '../../hooks/useAgentStream';
import { usePipelineState } from '../../hooks/usePipelineState';
import { AgentLog } from '../common/AgentLog';
import { StatusBadge } from '../common/StatusBadge';
import { ReviewPanel } from '../review/ReviewPanel';
import { ScriptViewer } from '../review/ScriptViewer';

interface Props {
  card: KanbanCard | null;
  onClose: () => void;
}

export function CardDrawer({ card, onClose }: Props) {
  const { thoughts, isConnected, bottomRef } = useAgentStream(card?.id ?? null);
  const { state, isWaitingForReview } = usePipelineState(card?.id ?? null);
  const drawerRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  if (!card) return null;

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
        className="fixed right-0 top-0 h-full w-[600px] max-w-[90vw] bg-gray-900 border-l border-gray-700 z-50 flex flex-col shadow-2xl animate-slide-in"
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-800 shrink-0">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-bold text-white truncate">
                {card.topic_brief?.title ?? 'Untitled'}
              </h2>
              <p className="text-sm text-gray-400 mt-1 line-clamp-2">
                {card.topic_brief?.description}
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
            {/* WebSocket connection indicator */}
            <span className={`text-xs ${isConnected ? 'text-green-400' : 'text-red-400'}`}>
              {isConnected ? '● Live' : '○ Disconnected'}
            </span>
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
              <ReviewPanel cardId={card.id} onDecision={onClose} />
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
