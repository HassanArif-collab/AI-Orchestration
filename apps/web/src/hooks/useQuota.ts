import useSWR from 'swr';
import { api } from '../lib/api';
import type { QuotaResponse } from '../types';
import { POLL_INTERVAL_MS } from '../lib/constants';

/**
 * Fetches live provider quotas every 5 seconds.
 *
 * Unlike agent thoughts (which use WebSocket), quotas come from
 * the FreeRouter SQLite DB via a REST endpoint. Polling is fine here
 * because quotas change slowly (once per LLM call, not per second).
 */
export function useQuota() {
  const { data, error, isLoading } = useSWR<QuotaResponse>(
    'provider-quota',
    () => api.getQuota(),
    {
      refreshInterval: POLL_INTERVAL_MS,
      revalidateOnFocus: true,
    }
  );

  return {
    providers: data?.providers ?? [],
    isLoading,
    error,
  };
}
