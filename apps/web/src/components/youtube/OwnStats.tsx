import { useOwnAnalytics } from '../../hooks/useYouTube';

export function OwnStats() {
  const { analytics, isLoading, error } = useOwnAnalytics();

  if (isLoading) return <div className="p-4 text-[hsl(var(--neutral-400))] text-sm">Loading your stats...</div>;
  if (error) return <div className="p-4 text-red-400 text-sm">YouTube API error: {String(error)}</div>;
  if (!analytics) return <div className="p-4 text-[hsl(var(--neutral-400))] text-sm">No analytics data available</div>;

  return (
    <div className="p-4 space-y-4">
      <h4 className="text-sm font-semibold text-[hsl(var(--neutral-400))]">Your Channel</h4>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 text-center border border-[hsl(var(--surface-glass-border))]">
          <p className="text-2xl font-bold text-[hsl(var(--neutral-100))]">
            {analytics.subscriber_count?.toLocaleString() ?? '—'}
          </p>
          <p className="text-xs text-[hsl(var(--neutral-500))]">Subscribers</p>
        </div>
        <div className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 text-center border border-[hsl(var(--surface-glass-border))]">
          <p className="text-2xl font-bold text-[hsl(var(--neutral-100))]">
            {analytics.total_views?.toLocaleString() ?? '—'}
          </p>
          <p className="text-xs text-[hsl(var(--neutral-500))]">Total Views</p>
        </div>
      </div>

      <div className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 text-center border border-[hsl(var(--surface-glass-border))]">
        <p className="text-xl font-bold text-[hsl(var(--neutral-100))]">
          {analytics.video_count?.toLocaleString() ?? '—'}
        </p>
        <p className="text-xs text-[hsl(var(--neutral-500))]">Videos</p>
      </div>
    </div>
  );
}
