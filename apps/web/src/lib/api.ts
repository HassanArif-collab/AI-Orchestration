import type { DiscoverRequest, ResumeRequest, PipelineStateResponse, QuotaResponse } from '../types';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000';

// ── Retry Configuration ──
const DEFAULT_TIMEOUT = 15_000; // 15 seconds
const MAX_RETRIES = 2;
const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504]);

interface RequestOptions extends RequestInit {
  timeout?: number;
  retries?: number;
}

/**
 * Core request wrapper with timeout and automatic retry.
 *
 * Features:
 * - AbortController-based timeout (default 15s)
 * - Automatic retry on 429/5xx with exponential backoff (max 2 retries)
 * - No retry on 4xx client errors (except 408 Request Timeout)
 * - Retries on network/timeout errors
 *
 * Error format is preserved: `API {status}: {body}` so downstream
 * errorMapper.ts can parse the status code from the message.
 */
async function request<T>(
  path: string,
  options: RequestOptions = {},
  currentRetry = 0,
): Promise<T> {
  const {
    timeout = DEFAULT_TIMEOUT,
    retries = MAX_RETRIES,
    ...fetchOptions
  } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  // Merge default JSON headers — callers rarely set Content-Type themselves
  const headers: Record<string, string> = {
    ...(fetchOptions.headers as Record<string, string>),
  };
  // Only set Content-Type for requests with a body (POST/PATCH/PUT)
  if (fetchOptions.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  try {
    const response = await fetch(`${BASE}${path}`, {
      ...fetchOptions,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Retry on server errors and rate limiting
    if (RETRYABLE_STATUS_CODES.has(response.status) && currentRetry < retries) {
      const backoffDelay = 1000 * Math.pow(2, currentRetry);
      console.warn(
        `[API] ${response.status} on ${path}. Retrying in ${backoffDelay}ms (attempt ${currentRetry + 1}/${retries})...`
      );
      await new Promise((resolve) => setTimeout(resolve, backoffDelay));
      return request<T>(path, options, currentRetry + 1);
    }

    // Handle non-ok responses (don't retry client errors)
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`API ${response.status}: ${body}`);
    }

    return response.json();
  } catch (err) {
    clearTimeout(timeoutId);

    // Retry on timeout or network errors
    const isRetryable =
      err instanceof Error &&
      (err.name === 'AbortError' ||
        err.message.includes('fetch') ||
        err.message.includes('Failed to fetch') ||
        err.message.includes('NetworkError'));

    if (isRetryable && currentRetry < retries) {
      const backoffDelay = 1000 * Math.pow(2, currentRetry);
      console.warn(
        `[API] Request to ${path} failed (${err.name}). Retrying in ${backoffDelay}ms (attempt ${currentRetry + 1}/${retries})...`
      );
      await new Promise((resolve) => setTimeout(resolve, backoffDelay));
      return request<T>(path, options, currentRetry + 1);
    }

    throw err;
  }
}

// ── Pipeline Endpoints ──

export const api = {
  // Trigger topic discovery
  discover: (body: DiscoverRequest) =>
    request<{ status: string; card_id: string }>('/api/pipeline/discover', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // Start production pipeline for a card
  produce: (cardId: string) =>
    request<{ status: string; card_id: string }>(`/api/pipeline/produce/${cardId}`, {
      method: 'POST',
    }),

  // Resume after human review
  resume: (cardId: string, decision: ResumeRequest) =>
    request<{ status: string }>(`/api/pipeline/langgraph/resume/${cardId}`, {
      method: 'POST',
      body: JSON.stringify(decision),
    }),

  // Get current LangGraph state
  getPipelineState: (cardId: string) =>
    request<PipelineStateResponse>(`/api/pipeline/langgraph/state/${cardId}`),

  // Get live provider quotas
  getQuota: () =>
    request<QuotaResponse>('/api/providers/quota'),

  // Get skill file contents (for System Editor)
  getSkills: () =>
    request<{ files: { name: string; content: string }[] }>('/api/settings/skills'),

  // Save a suggested topic (prevents 3-hour auto-delete)
  saveCard: (cardId: string) =>
    request<{ status: string }>(`/api/kanban/cards/${cardId}/save`, {
      method: 'POST',
    }),

  // Delete an expired/unwanted card
  deleteCard: (cardId: string) =>
    request<{ status: string }>(`/api/kanban/tasks/${cardId}`, {
      method: 'DELETE',
    }),

  // Move card between columns (canonical endpoint for drag-and-drop)
  moveCard: (cardId: string, toColumn: number) =>
    request<{ status: string }>(`/api/kanban/tasks/${cardId}`, {
      method: 'PATCH',
      body: JSON.stringify({ stage: toColumn }),
    }),

  // Get all kanban tasks
  getTasks: () =>
    request<{ tasks: unknown[] }>('/api/kanban/tasks'),

  // Get kanban stats
  getStats: () =>
    request<{ total_tasks: number; by_stage: Record<number, number>; by_status: Record<string, number> }>('/api/kanban/stats'),

  // ── YouTube Analytics ──

  getCompetitorVideos: () =>
    request<{ videos: unknown[] }>('/api/analytics/competitors'),

  getOwnAnalytics: (channelId?: string) =>
    request<{ subscriber_count: number; total_views: number; video_count: number }>(
      channelId ? `/api/analytics/channel?channel_id=${channelId}` : '/api/analytics/channel',
    ),

  repurposeVideo: (body: { title: string; video_id: string; channel: string; views: number }) =>
    request<{ status: string; card_id: string | null }>('/api/analytics/repurpose', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // ── Knowledge Base ──

  getKnowledgeBase: () =>
    request<{ content: string; path: string | null }>('/api/settings/knowledge-base'),
};
