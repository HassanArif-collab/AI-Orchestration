import type { ProviderQuota } from '@/lib/api';
import { useQuota } from '@/hooks/useQuota';
import { TableRowSkeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/utils';

/**
 * Returns color classes based on the remaining quota value.
 * - Green (healthy): remaining >= 50 or unlimited (-1)
 * - Yellow (warning): remaining >= 10 and < 50
 * - Red (critical): remaining < 10
 */
function getQuotaColorClass(remaining: number): { bg: string; text: string; bar: string } {
  if (remaining === -1) {
    return { bg: 'bg-emerald-500/20', text: 'text-emerald-400', bar: 'bg-emerald-500/60' };
  }
  if (remaining >= 50) {
    return { bg: 'bg-emerald-500/20', text: 'text-emerald-400', bar: 'bg-emerald-500/60' };
  }
  if (remaining >= 10) {
    return { bg: 'bg-amber-500/20', text: 'text-amber-400', bar: 'bg-amber-500/60' };
  }
  return { bg: 'bg-red-500/20', text: 'text-red-400', bar: 'bg-red-500/60' };
}

/**
 * Visual bar representing remaining quota.
 * For unlimited, shows full bar. For known values, maps to a proportional fill.
 */
function QuotaBar({ remaining, label }: { remaining: number; label: string }) {
  const colors = getQuotaColorClass(remaining);

  if (remaining === -1) {
    return (
      <span className={cn('px-2 py-0.5 rounded-md', colors.bg, colors.text)}>
        {label}: unlimited
      </span>
    );
  }

  // Map remaining to a visual fill: 0-100+ → 0-100%
  const fillPercent = Math.min(100, Math.max(0, remaining));

  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between mb-1">
        <span className={cn('text-xs font-mono', colors.text)}>{label}: {remaining.toLocaleString()}</span>
      </div>
      <div className="h-1.5 rounded-full bg-[hsl(var(--neutral-800))] overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-500', colors.bar)}
          style={{ width: `${fillPercent}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Displays live RPM/TPM remaining for each AI provider.
 *
 * Data comes from /api/v1/router/quota endpoint,
 * which reads actual HTTP response headers — zero hardcoding.
 *
 * -1 means the provider doesn't report limits (e.g., Ollama).
 * We display "Unlimited" for those.
 *
 * Color-coded bars provide at-a-glance health status:
 * - Green: healthy (remaining >= 50 or unlimited)
 * - Yellow: warning (remaining >= 10 and < 50)
 * - Red: critical (remaining < 10)
 */
export function QuotaPanel() {
  const { providers, isLoading, error } = useQuota();

  if (isLoading) return (
    <div className="p-4 space-y-5">
      <div className="h-4 w-36 bg-[hsl(var(--neutral-800))] rounded animate-pulse" />
      {[1, 2, 3].map((i) => (
        <TableRowSkeleton key={i} />
      ))}
    </div>
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
        <div key={provider.name} className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-[hsl(var(--neutral-100))] font-medium capitalize">
              {provider.name}
            </span>
            <span className="text-xs text-[hsl(var(--neutral-500))]">
              {new Date(provider.last_updated).toLocaleTimeString()}
            </span>
          </div>

          <div className="flex flex-col gap-2">
            <QuotaBar remaining={provider.rpm_remaining} label="RPM" />
            <QuotaBar remaining={provider.tpm_remaining} label="TPM" />
          </div>
        </div>
      ))}
    </div>
  );
}
