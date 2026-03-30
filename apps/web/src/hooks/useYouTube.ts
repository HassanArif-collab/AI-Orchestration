import useSWR from 'swr';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000';

export interface CompetitorVideo {
  title: string;
  video_id: string;
  channel_title: string;
  views: number;
  published_at: string;
  thumbnail_url?: string;
}

export interface OwnAnalytics {
  subscriber_count: number;
  total_views: number;
  video_count: number;
  channel_title?: string;
}

async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export function useCompetitorVideos() {
  const { data, error, isLoading } = useSWR(
    `${API_BASE}/api/analytics/competitors`,
    fetcher<{ videos?: CompetitorVideo[]; error?: string }>,
    { refreshInterval: 300_000 } // Refresh every 5 minutes
  );

  return {
    videos: (data?.videos ?? []) as CompetitorVideo[],
    isLoading,
    error: data?.error || error,
  };
}

export function useOwnAnalytics(channelId?: string) {
  const url = channelId
    ? `${API_BASE}/api/analytics/channel?channel_id=${channelId}`
    : `${API_BASE}/api/analytics/channel`;

  const { data, error, isLoading } = useSWR(
    url,
    fetcher<OwnAnalytics & { error?: string }>,
    { refreshInterval: 300_000 }
  );

  return {
    analytics: data as OwnAnalytics | null,
    isLoading,
    error: data?.error || error,
  };
}

export async function repurposeVideo(video: {
  title: string;
  video_id: string;
  channel_title: string;
  views: number;
}): Promise<{ status: string; card_id?: string }> {
  const res = await fetch(`${API_BASE}/api/analytics/repurpose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: video.title,
      video_id: video.video_id,
      channel: video.channel_title,
      views: video.views,
    }),
  });
  return res.json();
}
