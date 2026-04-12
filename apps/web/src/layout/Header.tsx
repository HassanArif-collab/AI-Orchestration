// apps/web/src/layout/Header.tsx
//
// Top application bar with global search and Discover Topics action.
//
// Styling directives (from Phase 2 spec):
// - Higher Z-axis: bg-[hsl(var(--surface-glass))] + backdrop-blur-md
// - Border: border-[hsl(var(--surface-glass-border))]
// - Z-index: z-[var(--z-header)]
//
// Features:
// - Global search bar → writes to useAppStore.searchQuery (consumed by Kanban board filter)
// - "Discover New Topics" button → POST /api/pipeline/discover
// - HealthBar integration (service status badge)
// - Lucide icons ONLY (no emojis, no FontAwesome)

import { useState } from 'react';
import { Search, Sparkles, Loader2, Clapperboard } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/lib/store';
import { discoverTopics } from '@/lib/api';
import { mapApiError } from '@/lib/errorMapper';
import { showToast } from '@/hooks/useToast';
import { HealthBar } from '@/components/system/HealthBar';

export function Header() {
  const [seedHint, setSeedHint] = useState('');
  const [isDiscovering, setIsDiscovering] = useState(false);

  // Global search query from Zustand store
  const searchQuery = useAppStore((s) => s.searchQuery);
  const setSearchQuery = useAppStore((s) => s.setSearchQuery);

  const handleDiscover = async () => {
    setIsDiscovering(true);
    try {
      await discoverTopics(seedHint || undefined);
      setSeedHint('');
      showToast({ type: 'success', title: 'Discovery started', message: 'Finding trending topics...' });
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({ type: 'error', title: friendlyError.title, message: friendlyError.message });
    } finally {
      setIsDiscovering(false);
    }
  };

  return (
    <header
      className={cn(
        'h-16 w-full shrink-0 flex items-center justify-between px-4 gap-4',
        'border-b border-[hsl(var(--surface-glass-border))]',
        'bg-[hsl(var(--surface-glass))] backdrop-blur-md',
        'z-[var(--z-header)]',
      )}
    >
      {/* Left: Brand */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <Clapperboard className="w-5 h-5 text-[hsl(var(--brand-500))]" strokeWidth={1.5} />
          <h1 className="text-lg font-semibold tracking-tight text-[hsl(var(--neutral-100))]">
            Content Factory
          </h1>
        </div>
        <span className="text-[10px] font-medium tracking-wide uppercase text-[hsl(var(--neutral-400))] bg-[hsl(var(--neutral-800))] px-2 py-0.5 rounded-md">
          FreeRouter AI
        </span>
      </div>

      {/* Center: Global Search */}
      <div className="flex-1 max-w-md">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(var(--neutral-400))]" strokeWidth={1.5} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search cards..."
            className={cn(
              'w-full pl-9 pr-3 py-2 rounded-lg text-sm',
              'bg-[hsl(var(--neutral-800))] border border-[hsl(var(--surface-glass-border))]',
              'text-[hsl(var(--neutral-100))] placeholder:text-[hsl(var(--neutral-400))]',
              'transition-all duration-[var(--duration-default)] ease-[var(--ease-spring)]',
              'focus:outline-none focus:ring-2 focus:ring-[hsl(var(--brand-500)/0.4)] focus:border-[hsl(var(--brand-500)/0.4)]',
            )}
            aria-label="Search kanban cards"
          />
        </div>
      </div>

      {/* Right: Discover + Health */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Seed hint input (optional) */}
        <input
          type="text"
          value={seedHint}
          onChange={(e) => setSeedHint(e.target.value)}
          placeholder="Seed hint (optional)"
          onKeyDown={(e) => e.key === 'Enter' && handleDiscover()}
          className={cn(
            'w-52 px-3 py-2 rounded-lg text-sm',
            'bg-[hsl(var(--neutral-800))] border border-[hsl(var(--surface-glass-border))]',
            'text-[hsl(var(--neutral-100))] placeholder:text-[hsl(var(--neutral-400))]',
            'transition-all duration-[var(--duration-default)] ease-[var(--ease-spring)]',
            'focus:outline-none focus:ring-2 focus:ring-[hsl(var(--brand-500)/0.4)] focus:border-[hsl(var(--brand-500)/0.4)]',
          )}
          aria-label="Seed hint for topic discovery"
        />

        {/* Discover Topics Button */}
        <button
          onClick={handleDiscover}
          disabled={isDiscovering}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white',
            'bg-[hsl(var(--brand-500))] hover:bg-[hsl(var(--brand-500)/0.85)]',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-all duration-[var(--duration-default)] ease-[var(--ease-spring)]',
            'shadow-[var(--shadow-glass)] hover:shadow-[var(--shadow-glow)]',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
          )}
          aria-label="Discover new topics"
        >
          {isDiscovering ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} />
              <span>Discovering...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" strokeWidth={1.5} />
              <span>Discover New Topics</span>
            </>
          )}
        </button>

        {/* Health Status Badge */}
        <HealthBar />
      </div>
    </header>
  );
}
