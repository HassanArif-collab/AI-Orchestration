import { Target, BarChart3 } from 'lucide-react';
import { useState } from 'react';
import { useCompetitorVideos } from '../../hooks/useYouTube';
import { CompetitorCard } from './CompetitorCard';
import { OwnStats } from './OwnStats';
import { cn } from '@/lib/utils';

type Tab = 'competitors' | 'own';

export function YouTubePanel() {
  const [tab, setTab] = useState<Tab>('competitors');
  const { videos, isLoading, error } = useCompetitorVideos();

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-[hsl(var(--surface-glass-border))] shrink-0 bg-[hsl(var(--surface-glass))] backdrop-blur-md">
        <button
          onClick={() => setTab('competitors')}
          className={cn(
            'flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors',
            tab === 'competitors'
              ? 'text-[hsl(var(--neutral-100))] border-b-2 border-[hsl(var(--brand-500))]'
              : 'text-[hsl(var(--neutral-500))] hover:text-[hsl(var(--neutral-300))]',
          )}
        >
          <Target className="w-3 h-3" strokeWidth={1.5} />
          Competitors
        </button>
        <button
          onClick={() => setTab('own')}
          className={cn(
            'flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors',
            tab === 'own'
              ? 'text-[hsl(var(--neutral-100))] border-b-2 border-[hsl(var(--brand-500))]'
              : 'text-[hsl(var(--neutral-500))] hover:text-[hsl(var(--neutral-300))]',
          )}
        >
          <BarChart3 className="w-3 h-3" strokeWidth={1.5} />
          Your Channel
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'competitors' && (
          <div className="p-3 space-y-3">
            <h3 className="text-sm font-semibold text-[hsl(var(--neutral-400))]">
              Competitor Latest Videos
            </h3>
            <p className="text-xs text-[hsl(var(--neutral-500))]">
              Click &quot;Repurpose&quot; to create a Kanban card for adaptation.
            </p>

            {isLoading && (
              <div className="space-y-3">
                <div className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 border border-[hsl(var(--surface-glass-border))] animate-pulse">
                  <div className="h-32 bg-[hsl(var(--neutral-800))] rounded-lg mb-2" />
                  <div className="h-4 bg-[hsl(var(--neutral-800))] rounded w-3/4" />
                  <div className="h-3 bg-[hsl(var(--neutral-800))] rounded w-1/2 mt-2" />
                </div>
              </div>
            )}
            {!isLoading && error && <p className="text-red-400 text-sm">{String(error)}</p>}
            {!isLoading && !error && videos.map((video) => (
              <CompetitorCard key={video.video_id} video={video} />
            ))}

            {!isLoading && videos.length === 0 && (
              <p className="text-[hsl(var(--neutral-500))] text-sm text-center mt-8">
                No competitor videos found. Check YouTube API configuration.
              </p>
            )}
          </div>
        )}

        {tab === 'own' && <OwnStats />}
      </div>
    </div>
  );
}
