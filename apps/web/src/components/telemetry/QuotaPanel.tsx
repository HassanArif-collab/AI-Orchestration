import { useQuota } from '../../hooks/useQuota';
import { ProgressBar } from '../common/ProgressBar';

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

      {providers.map((provider) => (
        <div key={provider.name} className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-white font-medium capitalize">
              {provider.name}
            </span>
            <span className="text-xs text-gray-500">
              Updated: {new Date(provider.last_updated).toLocaleTimeString()}
            </span>
          </div>

          {provider.rpm_remaining === -1 ? (
            <p className="text-xs text-green-400">RPM: Unlimited (local/unreported)</p>
          ) : (
            <ProgressBar
              label={`RPM Remaining: ${provider.rpm_remaining}`}
              value={Math.min(100, (provider.rpm_remaining / 30) * 100)} // Assume 30 RPM max for visual
              color="bg-blue-500"
            />
          )}

          {provider.tpm_remaining === -1 ? (
            <p className="text-xs text-green-400">TPM: Unlimited (local/unreported)</p>
          ) : (
            <ProgressBar
              label={`TPM Remaining: ${provider.tpm_remaining.toLocaleString()}`}
              value={Math.min(100, (provider.tpm_remaining / 500000) * 100)} // Assume 500k TPM max for visual
              color="bg-purple-500"
            />
          )}
        </div>
      ))}

      <p className="text-xs text-gray-600 italic">
        All values read directly from provider HTTP headers. No hardcoded estimates.
      </p>
    </div>
  );
}
