import { useOwnAnalytics } from '../../hooks/useYouTube';

export function OwnStats() {
  const { analytics, isLoading, error } = useOwnAnalytics();

  if (isLoading) return <div className="p-4 text-gray-500 text-sm">Loading your stats...</div>;
  if (error) return <div className="p-4 text-red-400 text-sm">YouTube API error: {String(error)}</div>;
  if (!analytics) return <div className="p-4 text-gray-500 text-sm">No analytics data available</div>;

  return (
    <div className="p-4 space-y-4">
      <h4 className="text-sm font-semibold text-gray-400">Your Channel</h4>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-white">
            {analytics.subscriber_count?.toLocaleString() ?? '—'}
          </p>
          <p className="text-xs text-gray-500">Subscribers</p>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-white">
            {analytics.total_views?.toLocaleString() ?? '—'}
          </p>
          <p className="text-xs text-gray-500">Total Views</p>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg p-3 text-center">
        <p className="text-xl font-bold text-white">
          {analytics.video_count?.toLocaleString() ?? '—'}
        </p>
        <p className="text-xs text-gray-500">Videos</p>
      </div>
    </div>
  );
}
