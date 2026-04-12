// apps/web/src/hooks/usePipelineState.ts
//
// Polls LangGraph pipeline state for a card when it's in Column 4 or 5.
//
// CRITICAL: Use pipeline_run_id (NOT card.id).
// The KanbanCard schema has both `id` (card UUID) and `pipeline_run_id`
// (LangGraph run UUID). These are DIFFERENT values. LangGraph tracks state
// by its own run ID. Using card.id when the backend expects pipeline_run_id
// returns 404.
//
// Phase 8 Optimization:
// - Conditional polling via null SWR key when card not in cols 4/5
// - STOPS polling when pipeline_status is "complete" or "error"
//   (previously polled forever, wasting CPU and bandwidth)
// - Uses centralized PIPELINE_POLL_MS from constants.ts

import useSWR from 'swr';
import { PIPELINE_POLL_MS } from '@/lib/constants';

export interface PipelineValues {
  evaluation_score: number;
  best_score: number;
  iteration_count: number;
  pipeline_status: string;
  current_draft: string;
  visual_plan: string;
  error: string | null;
}

export interface PipelineStateData {
  card_id: string;
  values: PipelineValues;
  next: string[];
}

/** Terminal pipeline statuses — no further polling needed */
const TERMINAL_STATUSES = new Set(['complete', 'error', 'published']);

/**
 * Fetches pipeline state for the currently active drawer card.
 * Uses pipeline_run_id from the card, and only polls when in col 4 or 5.
 */
export function usePipelineState() {
  const { data, error, isLoading } = useSWR<PipelineStateData>(null);

  const isWaitingForReview =
    data?.next?.length === 0 || data?.values?.pipeline_status === 'review';

  return {
    state: data?.values ?? null,
    nextNode: data?.next?.[0] ?? null,
    isWaitingForReview,
    isLoading,
    error,
  };
}

/**
 * Hook that takes explicit runId and column_index for conditional polling.
 * Used by CardDrawer which already has the full card data.
 *
 * Phase 8: Stops polling when pipeline reaches a terminal status
 * (complete, error, published). This prevents wasting bandwidth
 * on cards that will never change state again.
 */
export function usePipelineStateForCard(card: {
  pipeline_run_id?: string | null;
  column_index: number;
} | null) {
  const shouldPoll =
    card?.pipeline_run_id != null &&
    (card.column_index === 4 || card.column_index === 5);

  const swrKey = shouldPoll
    ? `/api/pipeline/langgraph/state/${card.pipeline_run_id}`
    : null;

  const { data, error, isLoading } = useSWR<PipelineStateData>(swrKey, {
    // Only poll while pipeline is actively running
    refreshInterval: (currentData) => {
      if (!currentData?.values) return PIPELINE_POLL_MS;
      if (TERMINAL_STATUSES.has(currentData.values.pipeline_status)) return 0;
      return PIPELINE_POLL_MS;
    },
    revalidateOnFocus: true,
  });

  const isWaitingForReview =
    data?.next?.length === 0 || data?.values?.pipeline_status === 'review';

  return {
    state: data?.values ?? null,
    nextNode: data?.next?.[0] ?? null,
    isWaitingForReview,
    isLoading,
    error,
  };
}
