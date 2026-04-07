import { useState } from 'react';
import { ExternalLink, RefreshCw } from 'lucide-react';
import type { CompetitorVideo } from '@/hooks/useYouTube';
import { repurposeVideo } from '@/lib/api';
import { mapApiError } from '@/lib/errorMapper';
import { showToast } from '@/hooks/useToast';
import { cn } from '@/lib/utils';

interface Props {
  video: CompetitorVideo;
}

export function CompetitorCard({ video }: Props) {
  const [isRepurposing, setIsRepurposing] = useState(false);
  const [repurposed, setRepurposed] = useState(false);

  const handleRepurpose = async () => {
    setIsRepurposing(true);
    try {
      const result = await repurposeVideo({
        title: video.title,
        video_id: video.video_id,
        channel: video.channel_title,
        views: video.views,
      });
      setRepurposed(true);
      if (result.card_id) {
        showToast({ type: 'success', title: 'Card created', message: 'Repurposed video added to pipeline.' });
      }
    } catch (err) {
      const friendlyError = mapApiError(err);
      showToast({ type: 'error', title: 'Repurpose failed', message: friendlyError.message });
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
    <div className="bg-[hsl(var(--surface-glass))] rounded-xl p-3 border border-[hsl(var(--surface-glass-border))]">
      {video.thumbnail_url && (
        <img src={video.thumbnail_url} alt={video.title} className="w-full h-32 object-cover rounded-lg mb-2" />
      )}
      <h4 className="text-sm text-[hsl(var(--neutral-100))] font-medium line-clamp-2">{video.title}</h4>
      <div className="flex items-center justify-between mt-2 text-xs text-[hsl(var(--neutral-500))]">
        <span>{video.channel_title}</span>
        <span>{formattedViews} views</span>
      </div>
      <p className="text-xs text-[hsl(var(--neutral-500))] mt-1">{new Date(video.published_at).toLocaleDateString()}</p>

      <div className="flex gap-2 mt-3">
        <a
          href={`https://youtube.com/watch?v=${video.video_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            'flex-1 flex items-center justify-center gap-1.5 text-xs',
            'bg-[hsl(var(--neutral-800))] hover:bg-[hsl(var(--neutral-700))] text-[hsl(var(--neutral-100))]',
            'py-1.5 rounded-lg transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
          )}
        >
          <ExternalLink className="w-3 h-3" strokeWidth={1.5} />
          Watch
        </a>
        <button
          onClick={handleRepurpose}
          disabled={isRepurposing || repurposed}
          className={cn(
            'flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5 rounded-lg font-medium transition-all',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500))]',
            repurposed
              ? 'bg-emerald-500/20 text-emerald-300 cursor-default'
              : 'bg-[hsl(var(--brand-500))] hover:bg-[hsl(var(--brand-300))] text-white',
            'disabled:opacity-50 disabled:cursor-not-allowed',
          )}
        >
          {repurposed ? (
            'Added'
          ) : isRepurposing ? (
            <RefreshCw className="w-3 h-3 animate-spin" strokeWidth={1.5} />
          ) : (
            'Repurpose'
          )}
        </button>
      </div>
    </div>
  );
}
