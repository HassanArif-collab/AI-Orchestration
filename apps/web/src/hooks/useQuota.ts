import useSWR from 'swr';
import { getQuota } from '@/lib/api';
import type { QuotaResponse } from '@/lib/api';

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
    () => getQuota(),
    {
      refreshInterval: 5_000,
      revalidateOnFocus: true,
    }
  );

  return {
    providers: data?.providers ?? [],
    isLoading,
    error,
  };
}
