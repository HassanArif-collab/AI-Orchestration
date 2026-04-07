import useSWR from 'swr';
import { getProviderModels, type ProviderModel } from '@/lib/api';
import { TableRowSkeleton } from '@/components/ui/Skeleton';

/**
 * Read-only display of which agent uses which model on which provider.
 * Fetches data dynamically from /api/providers/models instead of
 * using a hardcoded static array.
 */
export function ModelRegistry() {
  const { data, isLoading, error } = useSWR('provider-models', () => getProviderModels());

  if (isLoading) {
    return (
      <div className="p-4">
        <h3 className="text-sm font-semibold text-[hsl(var(--neutral-400))] mb-3">Agent / Model Mapping</h3>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <TableRowSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <h3 className="text-sm font-semibold text-[hsl(var(--neutral-400))] mb-3">Agent / Model Mapping</h3>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3">
          <p className="text-red-300 text-sm font-medium">Failed to load model registry</p>
          <p className="text-red-200/70 text-xs mt-1">{String(error)}</p>
        </div>
      </div>
    );
  }

  const models: ProviderModel[] = data?.models ?? [];

  if (models.length === 0) {
    return (
      <div className="p-4">
        <h3 className="text-sm font-semibold text-[hsl(var(--neutral-400))] mb-3">Agent / Model Mapping</h3>
        <p className="text-[hsl(var(--neutral-500))] text-sm text-center py-6">
          No model mappings configured yet.
        </p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h3 className="text-sm font-semibold text-[hsl(var(--neutral-400))] mb-3">Agent / Model Mapping</h3>

      <div className="space-y-3">
        {models.map((entry) => {
          const provider = entry.model.split('/')[0] ?? 'unknown';

          return (
            <div key={entry.task} className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 border border-[hsl(var(--surface-glass-border))]">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[hsl(var(--neutral-100))] font-medium capitalize">{entry.task}</span>
                <span className="text-xs bg-[hsl(var(--neutral-800))] text-[hsl(var(--neutral-300))] px-2 py-0.5 rounded-md border border-[hsl(var(--surface-glass-border))] capitalize">
                  {provider}
                </span>
              </div>
              <p className="text-xs text-[hsl(var(--lineage-cyan))] font-mono mt-1">{entry.model}</p>
              {entry.fallback && (
                <p className="text-xs text-[hsl(var(--neutral-500))] mt-1">
                  Fallback: <span className="font-mono text-[hsl(var(--neutral-400))]">{entry.fallback}</span>
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
