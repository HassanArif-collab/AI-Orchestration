import { MODEL_REGISTRY } from '@/types';

/**
 * Read-only display of which agent uses which model on which provider.
 * Data is static (from Phase 3c assignments). Shows the user
 * why certain models are chosen for certain tasks.
 */
export function ModelRegistry() {
  return (
    <div className="p-4">
      <h3 className="text-sm font-semibold text-[hsl(var(--neutral-400))] mb-3">Agent / Model Mapping</h3>

      <div className="space-y-3">
        {MODEL_REGISTRY.map((entry) => (
          <div key={entry.agent} className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 border border-[hsl(var(--surface-glass-border))]">
            <div className="flex items-center justify-between">
              <span className="text-sm text-[hsl(var(--neutral-100))] font-medium">{entry.agent}</span>
              <span className="text-xs bg-[hsl(var(--neutral-800))] text-[hsl(var(--neutral-300))] px-2 py-0.5 rounded-md border border-[hsl(var(--surface-glass-border))]">
                {entry.provider}
              </span>
            </div>
            <p className="text-xs text-[hsl(var(--lineage-cyan))] font-mono mt-1">{entry.model}</p>
            <p className="text-xs text-[hsl(var(--neutral-500))] mt-1">{entry.reason}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
