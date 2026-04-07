import type { ProviderQuota } from '@/lib/api';
import { useQuota } from '@/hooks/useQuota';
import { cn } from '@/lib/utils';

/**
 * Displays live RPM/TPM remaining for each AI provider.
 *
 * Data comes from /api/v1/router/quota endpoint,
 * which reads actual HTTP response headers — zero hardcoding.
 *
 * -1 means the provider doesn't report limits (e.g., Ollama).
 * We display "Unlimited" for those.
 *
 * Shows raw remaining values — no misleading percentage bars since
 * actual provider limits vary and cannot be accurately represented
 * with fixed denominators.
 */
export function QuotaPanel() {
  const { providers, isLoading, error } = useQuota();

  if (isLoading) return (
    <div className="p-4 text-[hsl(var(--neutral-400))] text-sm">Loading quotas...</div>
  );
  if (error) return (
    <div className="p-4 text-red-400 text-sm">Failed to load quotas</div>
  );
  if (providers.length === 0) return (
    <div className="p-4 text-[hsl(var(--neutral-400))] text-sm">No provider data yet</div>
  );

  return (
    <div className="p-4 space-y-5">
      <h3 className="text-sm font-semibold text-[hsl(var(--neutral-400))]">Live Provider Quotas</h3>

      {providers.map((provider: ProviderQuota) => (
        <div key={provider.name} className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-[hsl(var(--neutral-100))] font-medium capitalize">
              {provider.name}
            </span>
            <span className="text-xs text-[hsl(var(--neutral-500))]">
              {new Date(provider.last_updated).toLocaleTimeString()}
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono">
            <span className={cn(
              'px-2 py-0.5 rounded-md',
              provider.rpm_remaining === -1
                ? 'bg-emerald-500/10 text-emerald-400'
                : 'bg-[hsl(var(--neutral-800))] text-[hsl(var(--neutral-300))]',
            )}>
              {provider.rpm_remaining === -1 ? 'RPM: unlimited' : `RPM: ${provider.rpm_remaining}`}
            </span>
            <span className={cn(
              'px-2 py-0.5 rounded-md',
              provider.tpm_remaining === -1
                ? 'bg-emerald-500/10 text-emerald-400'
                : 'bg-[hsl(var(--neutral-800))] text-[hsl(var(--neutral-300))]',
            )}>
              {provider.tpm_remaining === -1
                ? 'TPM: unlimited'
                : `TPM: ${provider.tpm_remaining.toLocaleString()}`
              }
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
