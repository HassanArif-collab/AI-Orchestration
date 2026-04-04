import { useState } from 'react';
import { useCompetitorVideos } from '../../hooks/useYouTube';
import { CompetitorCard } from './CompetitorCard';
import { OwnStats } from './OwnStats';

type Tab = 'competitors' | 'own';

export function YouTubePanel() {
  const [tab, setTab] = useState<Tab>('competitors');
  const { videos, isLoading, error } = useCompetitorVideos();

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-gray-800 shrink-0">
        <button
          onClick={() => setTab('competitors')}
          className={`flex-1 py-2 text-xs font-medium ${
            tab === 'competitors' ? 'text-white border-b-2 border-blue-500' : 'text-gray-500'
          }`}
        >
          🎯 Competitors
        </button>
        <button
          onClick={() => setTab('own')}
          className={`flex-1 py-2 text-xs font-medium ${
            tab === 'own' ? 'text-white border-b-2 border-blue-500' : 'text-gray-500'
          }`}
        >
          📊 Your Channel
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {tab === 'competitors' && (
          <div className="p-3 space-y-3">
            <h3 className="text-sm font-semibold text-gray-400">
              Competitor Latest Videos
            </h3>
            <p className="text-xs text-gray-600">
              Click "Repurpose" to create a Kanban card for adaptation.
            </p>

            {isLoading && (
              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3 border border-gray-700 animate-pulse">
                  <div className="h-32 bg-gray-700 rounded mb-2" />
                  <div className="h-4 bg-gray-700 rounded w-3/4" />
                  <div className="h-3 bg-gray-700 rounded w-1/2 mt-2" />
                </div>
              </div>
            )}
            {!isLoading && error && <p className="text-red-400 text-sm">{String(error)}</p>}
            {!isLoading && !error && videos.map((video) => (
              <CompetitorCard key={video.video_id} video={video} />
            ))}

            {!isLoading && videos.length === 0 && (
              <p className="text-gray-600 text-sm text-center mt-8">
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
