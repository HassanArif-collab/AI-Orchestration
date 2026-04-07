import useSWR from 'swr';
import { getQuota } from '@/lib/api';
import type { QuotaResponse } from '@/lib/api';
import { QUOTA_POLL_MS } from '@/lib/constants';
import { useAppStore } from '@/lib/store';

/**
 * Fetches live provider quotas.
 *
 * Phase 8 Optimization:
 * - Only polls when the Quota tab is visible in the sidebar.
 * - Uses Zustand activeTab to determine visibility.
 * - Stops polling entirely when user is on a different tab,
 *   saving bandwidth and preventing unnecessary backend load.
 *
 * When the Quota tab becomes visible again, SWR automatically
 * triggers a revalidation via revalidateOnFocus.
 */
export function useQuota() {
  const activeTab = useAppStore((s) => s.activeTab);
  const isQuotaTabVisible = activeTab === 'quota';

  const { data, error, isLoading } = useSWR<QuotaResponse>(
    // Null key disables SWR entirely (no fetch, no polling)
    isQuotaTabVisible ? 'provider-quota' : null,
    () => getQuota(),
    {
      refreshInterval: isQuotaTabVisible ? QUOTA_POLL_MS : 0,
      revalidateOnFocus: true,
    },
  );

  return {
    providers: data?.providers ?? [],
    isLoading,
    error,
  };
}
