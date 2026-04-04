import useSWR from 'swr';
import { api } from '../lib/api';
import type { PipelineStateResponse } from '../types';
import { POLL_INTERVAL_MS } from '../lib/constants';

/**
 * Fetches the current LangGraph checkpoint state for a card.
 *
 * Used by the CardDrawer to show:
 * - Current score and best score
 * - Iteration count (e.g., "Iteration 7/20")
 * - Which node is executing next
 * - Whether the graph is paused waiting for review
 */
export function usePipelineState(cardId: string | null) {
  const { data, error, isLoading } = useSWR<PipelineStateResponse>(
    cardId ? `pipeline-state-${cardId}` : null, // null key = don't fetch
    () => api.getPipelineState(cardId!),
    {
      refreshInterval: POLL_INTERVAL_MS,
      revalidateOnFocus: true,
    }
  );

  const isWaitingForReview = data?.next?.length === 0 || data?.values?.pipeline_status === 'review';

  return {
    state: data?.values ?? null,
    nextNode: data?.next?.[0] ?? null,
    isWaitingForReview,
    isLoading,
    error,
  };
}
