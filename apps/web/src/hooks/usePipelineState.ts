import useSWR from 'swr';
import { getPipelineState } from '@/lib/api';
import type { PipelineStateResponse } from '@/types';

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
    () => getPipelineState(cardId!),
    {
      refreshInterval: 5_000,
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
