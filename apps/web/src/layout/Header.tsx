import { useState } from 'react';
import { api } from '../lib/api';

export function Header() {
  const [seedHint, setSeedHint] = useState('');
  const [isDiscovering, setIsDiscovering] = useState(false);

  const handleDiscover = async () => {
    setIsDiscovering(true);
    try {
      await api.discover({ seed_hint: seedHint || undefined });
      setSeedHint('');
    } catch (err) {
      console.error('Discovery failed:', err);
    } finally {
      setIsDiscovering(false);
    }
  };

  return (
    <header className="h-14 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-3">
        <h1 className="text-white font-bold text-lg">🎬 Content Factory</h1>
        <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">
          FreeRouter AI
        </span>
      </div>

      {/* Topic Discovery Trigger */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={seedHint}
          onChange={(e) => setSeedHint(e.target.value)}
          placeholder="Optional seed hint (e.g., 'AI in Pakistan')..."
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white placeholder-gray-500 w-72"
          onKeyDown={(e) => e.key === 'Enter' && handleDiscover()}
        />
        <button
          onClick={handleDiscover}
          disabled={isDiscovering}
          className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 text-white px-4 py-1.5 rounded text-sm font-medium flex items-center gap-1"
        >
          {isDiscovering ? (
            <>
              <span className="animate-spin">⏳</span> Discovering...
            </>
          ) : (
            <>🔍 Discover Topics</>
          )}
        </button>
      </div>
    </header>
  );
}
