import useSWR from 'swr';
import { getCompetitorVideos, getOwnAnalytics } from '@/lib/api';
import { YOUTUBE_POLL_MS } from '@/lib/constants';

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

export function useCompetitorVideos(enabled: boolean = true) {
  const { data, error, isLoading } = useSWR(
    enabled ? 'competitor-videos' : null,
    () => getCompetitorVideos() as Promise<{ videos?: CompetitorVideo[]; error?: string }>,
    { refreshInterval: enabled ? YOUTUBE_POLL_MS : 0 }
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
    { refreshInterval: YOUTUBE_POLL_MS }
  );

  return {
    analytics: data as OwnAnalytics | null,
    isLoading,
    error: data?.error || error,
  };
}
