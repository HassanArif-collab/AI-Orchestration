import { useState } from 'react';
import type { CompetitorVideo } from '../../hooks/useYouTube';

interface Props {
  video: CompetitorVideo;
}

export function CompetitorCard({ video }: Props) {
  const [isRepurposing, setIsRepurposing] = useState(false);
  const [repurposed, setRepurposed] = useState(false);

  const handleRepurpose = async () => {
    setIsRepurposing(true);
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL || 'http://localhost:3000'}/api/analytics/repurpose`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: video.title,
            video_id: video.video_id,
            channel: video.channel_title,
            views: video.views,
          }),
        }
      );
      if (res.ok) {
        setRepurposed(true);
      }
    } catch (err) {
      console.error('Repurpose failed:', err);
    } finally {
      setIsRepurposing(false);
    }
  };

  const formattedViews = video.views >= 1_000_000
    ? `${(video.views / 1_000_000).toFixed(1)}M`
    : video.views >= 1_000
    ? `${(video.views / 1_000).toFixed(1)}K`
    : String(video.views);

  return (
    <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
      {/* Thumbnail */}
      {video.thumbnail_url && (
        <img
          src={video.thumbnail_url}
          alt={video.title}
          className="w-full h-32 object-cover rounded mb-2"
        />
      )}

      {/* Title */}
      <h4 className="text-sm text-white font-medium line-clamp-2">
        {video.title}
      </h4>

      {/* Meta */}
      <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
        <span>{video.channel_title}</span>
        <span>{formattedViews} views</span>
      </div>
      <p className="text-xs text-gray-600 mt-1">
        {new Date(video.published_at).toLocaleDateString()}
      </p>

      {/* Actions */}
      <div className="flex gap-2 mt-3">
        <a
          href={`https://youtube.com/watch?v=${video.video_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 text-center text-xs bg-gray-700 hover:bg-gray-600 text-white py-1.5 rounded"
        >
          ▶ Watch
        </a>
        <button
          onClick={handleRepurpose}
          disabled={isRepurposing || repurposed}
          className={`flex-1 text-xs py-1.5 rounded font-medium ${
            repurposed
              ? 'bg-green-800 text-green-300 cursor-default'
              : 'bg-blue-600 hover:bg-blue-500 text-white'
          } disabled:opacity-50`}
        >
          {repurposed ? '✓ Added' : isRepurposing ? '...' : 'Repurpose'}
        </button>
      </div>
    </div>
  );
}
