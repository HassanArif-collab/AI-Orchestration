import { MODEL_REGISTRY } from '@/types';

/**
 * Read-only display of which agent uses which model on which provider.
 * Data is static (from Phase 3c assignments). Shows the user
 * why certain models are chosen for certain tasks.
 */
export function ModelRegistry() {
  return (
    <div className="p-4">
      <h3 className="text-sm font-semibold text-gray-400 mb-3">Agent → Model Mapping</h3>

      <div className="space-y-3">
        {MODEL_REGISTRY.map((entry) => (
          <div key={entry.agent} className="bg-gray-800 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-white font-medium">{entry.agent}</span>
              <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                {entry.provider}
              </span>
            </div>
            <p className="text-xs text-cyan-400 font-mono mt-1">{entry.model}</p>
            <p className="text-xs text-gray-500 mt-1">{entry.reason}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
