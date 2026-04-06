import useSWR from 'swr';
import { getCompetitorVideos, getOwnAnalytics } from '@/lib/api';

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

export function useCompetitorVideos() {
  const { data, error, isLoading } = useSWR(
    'competitor-videos',
    () => getCompetitorVideos() as Promise<{ videos?: CompetitorVideo[]; error?: string }>,
    { refreshInterval: 300_000 } // Refresh every 5 minutes
  );

  return {
    videos: (data?.videos ?? []) as CompetitorVideo[],
    isLoading,
    error: data?.error || error,
  };
}

export function useOwnAnalytics(channelId?: string) {
  const key = channelId ? `own-analytics-${channelId}` : 'own-analytics';

  const { data, error, isLoading } = useSWR(
    key,
    () => getOwnAnalytics(channelId) as Promise<OwnAnalytics & { error?: string }>,
    { refreshInterval: 300_000 }
  );

  return {
    analytics: data as OwnAnalytics | null,
    isLoading,
    error: data?.error || error,
  };
}
