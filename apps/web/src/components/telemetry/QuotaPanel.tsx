import type { ProviderQuota } from '@/lib/api';
import { useQuota } from '@/hooks/useQuota';

/**
 * Displays live RPM/TPM remaining for each AI provider.
 *
 * Data comes from Phase 3's /api/v1/router/quota endpoint,
 * which reads actual HTTP response headers — zero hardcoding.
 *
 * -1 means the provider doesn't report limits (e.g., Ollama).
 * We display "Unlimited" for those.
 */
export function QuotaPanel() {
  const { providers, isLoading, error } = useQuota();

  if (isLoading) return <div className="p-4 text-gray-500 text-sm">Loading quotas...</div>;
  if (error) return <div className="p-4 text-red-400 text-sm">Failed to load quotas</div>;
  if (providers.length === 0) return <div className="p-4 text-gray-500 text-sm">No provider data yet</div>;

  return (
    <div className="p-4 space-y-6">
      <h3 className="text-sm font-semibold text-gray-400">Live Provider Quotas</h3>

      {providers.map((provider: ProviderQuota) => (
        <div key={provider.name} className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-white font-medium capitalize">
              {provider.name}
            </span>
            <span className="text-xs text-gray-500">
              Updated: {new Date(provider.last_updated).toLocaleTimeString()}
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <span className={`font-mono ${provider.rpm_remaining === -1 ? 'text-green-400' : 'text-gray-300'}`}>
              rpm: {provider.rpm_remaining === -1 ? '∞' : provider.rpm_remaining}
            </span>
            <span className={`font-mono ${provider.tpm_remaining === -1 ? 'text-green-400' : 'text-gray-300'}`}>
              tpm: {provider.tpm_remaining === -1 ? '∞' : provider.tpm_remaining.toLocaleString()}
            </span>
          </div>
        </div>
      ))}

    </div>
  );
}
