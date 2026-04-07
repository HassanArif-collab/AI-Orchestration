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
// Conditional Polling: The null key pattern disables SWR polling when
// no card is active or the card is not in columns 4/5.

import useSWR from 'swr';

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

/**
 * Fetches pipeline state for the currently active drawer card.
 * Uses pipeline_run_id from the card, and only polls when in col 4 or 5.
 */
export function usePipelineState() {
  // The parent component (CardDrawer) should use usePipelineStateForCard
  // which takes explicit runId and column_index.
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
 */
export function usePipelineStateForCard(card: {
  pipeline_run_id?: string | null;
  column_index: number;
} | null) {
  const key =
    card?.pipeline_run_id && (card.column_index === 4 || card.column_index === 5)
      ? `/api/pipeline/langgraph/state/${card.pipeline_run_id}`
      : null; // Don't poll if run hasn't started or card not in production

  const { data, error, isLoading } = useSWR<PipelineStateData>(key, {
    refreshInterval: 5_000,
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
