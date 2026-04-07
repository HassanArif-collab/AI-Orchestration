// apps/web/src/lib/api.ts
// Authenticated Fetch Wrapper + Typed API Endpoint Functions
//
// Every API call MUST go through apiFetch() which auto-injects
// Supabase JWT auth headers. The SWR global fetcher in main.tsx
// handles GET-only; apiFetch is for mutations.
//
// Phase 8: Centralized timeout (AbortController) + retry with
// exponential backoff for transient errors. All values from constants.ts.

import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import { env } from '@/config/env';
import {
  API_TIMEOUT_MS,
  MAX_RETRIES,
  RETRYABLE_STATUS_CODES,
  RETRY_DELAYS_MS,
} from '@/lib/constants';

// ─── Core Authenticated Fetch Wrapper ─────────────────────────────────────

/**
 * Authenticated fetch wrapper with timeout + retry.
 *
 * Features:
 * - Auto-attaches Supabase JWT Bearer header when configured
 * - AbortController timeout (15s default) prevents hanging requests
 * - Automatic retry on 408/429/5xx with exponential backoff (1s, 2s)
 * - JSON parse error handling with user-friendly messages
 */
export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit & { _skipRetry?: boolean },
): Promise<T> {
  let authToken: string | undefined;
  if (isSupabaseConfigured() && supabase) {
    const { data: { session } } = await supabase.auth.getSession();
    authToken = session?.access_token;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  // Merge caller's signal with our timeout signal
  const mergedSignal = init?.signal
    ? AbortSignal.any([init.signal, controller.signal])
    : controller.signal;

  let lastError: Error | null = null;
  const skipRetry = init?._skipRetry ?? false;

  for (let attempt = 0; attempt <= (skipRetry ? 0 : MAX_RETRIES); attempt++) {
    try {
      // Delay before retry (not on first attempt)
      if (attempt > 0) {
        await new Promise((resolve) =>
          setTimeout(resolve, RETRY_DELAYS_MS[attempt - 1] ?? 2_000),
        );
      }

      const res = await fetch(`${env.API_BASE_URL}${path}`, {
        ...init,
        signal: mergedSignal,
        headers: {
          'Content-Type': 'application/json',
          ...(authToken
            ? { Authorization: `Bearer ${authToken}` }
            : {}),
          ...init?.headers,
        },
      });

      // If the response is a transient error and we have retries left, retry
      if (
        !res.ok
        && !skipRetry
        && RETRYABLE_STATUS_CODES.includes(res.status)
        && attempt < MAX_RETRIES
      ) {
        lastError = new Error(`API ${res.status}: ${res.statusText} on ${path}`);
        continue; // retry
      }

      if (!res.ok) {
        clearTimeout(timeoutId);
        throw new Error(`API ${res.status}: ${res.statusText} on ${path}`);
      }

      clearTimeout(timeoutId);

      // Safe JSON parse with fallback
      try {
        return await res.json() as Promise<T>;
      } catch {
        throw new Error(`Failed to parse response from ${path}`);
      }
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));

      // Don't retry on abort (user-initiated cancel or timeout)
      if (lastError.name === 'AbortError') {
        clearTimeout(timeoutId);
        throw lastError;
      }

      // If this was the last attempt, throw
      if (attempt >= (skipRetry ? 0 : MAX_RETRIES)) {
        clearTimeout(timeoutId);
        throw lastError;
      }

      // Otherwise, continue to next retry iteration
    }
  }

  clearTimeout(timeoutId);
  throw lastError ?? new Error(`API request failed: ${path}`);
}

// ─── Typed Endpoint Wrappers ──────────────────────────────────────────────

// ── Pipeline Endpoints ──

/** Start a new topic discovery process (creates Column 1 cards). */
export function discoverTopics(seedHint?: string) {
  return apiFetch<{ status: string; card_id: string }>('/api/pipeline/discover', {
    method: 'POST',
    body: JSON.stringify({ seed_hint: seedHint }),
  });
}

/** User clicked "Save" on a Column 2 card (moves to Column 3, removes 3h expiry). */
export function saveCard(cardId: string) {
  return apiFetch<{ status: string }>(`/api/kanban/cards/${cardId}/save`, {
    method: 'POST',
  });
}

/** Add 3 hours to expiry for a topic. */
export function extendTaskExpiry(cardId: string) {
  return apiFetch<{ status: string }>(`/api/kanban/tasks/${cardId}/extend`, {
    method: 'POST',
  });
}

/** User dragged card from 3 to 4 (Start production LangGraph). */
export function startProduction(cardId: string) {
  return apiFetch<{ status: string; card_id: string }>(`/api/pipeline/produce/${cardId}`, {
    method: 'POST',
  });
}

// ── Drag & Drop (Optimistic UI fallback) ──

/** Move card. Payload: { stage: col_num, position: target_index }. */
export function moveCard(cardId: string, payload: { stage: number; position: number }) {
  return apiFetch<{ status: string }>(`/api/kanban/tasks/${cardId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

/** Soft delete task. */
export function deleteCard(cardId: string) {
  return apiFetch<{ status: string }>(`/api/kanban/tasks/${cardId}`, {
    method: 'DELETE',
  });
}

// ── Pipeline Monitoring & Human Gates ──

export type PipelineStateResponse = {
  card_id: string;
  values: {
    evaluation_score: number;
    best_score: number;
    iteration_count: number;
    pipeline_status: string;
    current_draft: string;
    visual_plan: string;
    error: string | null;
  };
  next: string[];
};

/** Poll every 5s while in Production. */
export function getPipelineState(runId: string) {
  return apiFetch<PipelineStateResponse>(`/api/pipeline/langgraph/state/${runId}`);
}

/** Approve/Reject script in the drawer. */
export function resumePipeline(
  cardId: string,
  payload: { approved: boolean; feedback?: string },
) {
  return apiFetch<{ status: string }>(
    `/api/pipeline/langgraph/resume/${cardId}`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

/** Final preview check. */
export function getPipelinePreview(cardId: string) {
  return apiFetch<PipelineStateResponse>(`/api/pipeline/langgraph/preview/${cardId}`);
}

// ── Provider / Quota Endpoints ──

export type ProviderQuota = {
  name: string;
  rpm_remaining: number;
  tpm_remaining: number;
  last_updated: string;
};

export type QuotaResponse = {
  providers: ProviderQuota[];
};

/** Get live provider quotas. */
export function getQuota() {
  return apiFetch<QuotaResponse>('/api/providers/quota');
}

// ── Provider Models Endpoint ──

export type ProviderModel = {
  task: string;
  model: string;
  fallback: string;
};

/** Get the agent/model mapping from the API (dynamic, not hardcoded). */
export function getProviderModels() {
  return apiFetch<{ models: ProviderModel[] }>('/api/providers/models');
}

// ── Settings Endpoints ──

/** Get skill file contents (for System Editor). */
export function getSkills() {
  return apiFetch<{ files: { name: string; content: string }[] }>('/api/settings/skills');
}

/** Get knowledge base content. */
export function getKnowledgeBase() {
  return apiFetch<{ content: string; path: string | null }>('/api/settings/knowledge-base');
}

// ── YouTube Analytics ──

/** Get competitor videos. */
export function getCompetitorVideos() {
  return apiFetch<{ videos: unknown[] }>('/api/analytics/competitors');
}

/** Get own channel analytics. */
export function getOwnAnalytics(channelId?: string) {
  const url = channelId
    ? `/api/analytics/channel?channel_id=${channelId}`
    : '/api/analytics/channel';
  return apiFetch<{
    subscriber_count: number;
    total_views: number;
    video_count: number;
  }>(url);
}

/** Repurpose a competitor video. */
export function repurposeVideo(body: {
  title: string;
  video_id: string;
  channel: string;
  views: number;
}) {
  return apiFetch<{ status: string; card_id: string | null }>('/api/analytics/repurpose', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ── DLQ Endpoints ──

/** Get DLQ statistics. */
export function getDLQStats() {
  return apiFetch<{ pending: number; total: number }>('/api/dlq/stats');
}

/** Get DLQ items by status. */
export function getDLQItems(status: string = 'pending') {
  return apiFetch<unknown[]>(`/api/dlq/items?status=${status}`);
}

/** Retry a failed DLQ item. */
export function retryDLQItem(itemId: string) {
  return apiFetch<{ status: string }>(`/api/dlq/items/${itemId}/retry`, {
    method: 'POST',
  });
}

/** Delete a DLQ item. */
export function deleteDLQItem(itemId: string) {
  return apiFetch<{ status: string }>(`/api/dlq/items/${itemId}`, {
    method: 'DELETE',
  });
}

// ── Provider Settings ──

/** Update a provider API key. */
export function updateProviderKey(providerName: string, apiKey: string) {
  return apiFetch<{ status: string }>(`/api/providers/${providerName}/key`, {
    method: 'POST',
    body: JSON.stringify({ api_key: apiKey }),
  });
}

/** Test a provider connection. */
export function testProviderConnection(providerName: string) {
  return apiFetch<{ status: string }>(`/api/providers/${providerName}/test`, {
    method: 'POST',
  });
}

// ── Topic Reservoir ──

/** Get the full topic reservoir. */
export function getTopicReservoir() {
  return apiFetch<unknown[]>('/api/topics/reservoir');
}

/** Bulk approve topics. */
export function approveTopics(topicIds: string[]) {
  return apiFetch<{ status: string }>('/api/topics/approve', {
    method: 'POST',
    body: JSON.stringify({ topic_ids: topicIds }),
  });
}

/** Bulk reject topics. */
export function rejectTopics(topicIds: string[]) {
  return apiFetch<{ status: string }>('/api/topics/reject', {
    method: 'POST',
    body: JSON.stringify({ topic_ids: topicIds }),
  });
}

// ── Memory / Zep Endpoints ──

/** Get Zep memory sessions. */
export function getMemorySessions() {
  return apiFetch<unknown[]>('/api/memory/sessions');
}

/** Get facts for a specific session. */
export function getMemoryFacts(sessionId: string) {
  return apiFetch<unknown[]>(`/api/memory/facts/${sessionId}`);
}

// ── Visual Config Endpoints ──

/** Get Remotion templates. */
export function getRemotionTemplates() {
  return apiFetch<unknown[]>('/api/visual/remotion/templates');
}

/** Get Radiant shaders. */
export function getRadiantShaders() {
  return apiFetch<unknown[]>('/api/visual/radiant/shaders');
}

// ── Iteration Logs ──

/** Get iteration logs for a pipeline run. */
export function getIterations(runId: string) {
  return apiFetch<unknown[]>(`/api/pipeline/iterations/${runId}`);
}

// ── Re-export for backward compatibility ──

/** @deprecated Use the individual named functions above instead. */
export const api = {
  discover: (body: { seed_hint?: string }) =>
    discoverTopics(body.seed_hint),
  produce: (cardId: string) =>
    startProduction(cardId),
  resume: (cardId: string, decision: { approved: boolean; feedback?: string }) =>
    resumePipeline(cardId, decision),
  getPipelineState: (cardId: string) =>
    getPipelineState(cardId),
  getQuota: () =>
    getQuota(),
  getSkills: () =>
    getSkills(),
  saveCard: (cardId: string) =>
    saveCard(cardId),
  deleteCard: (cardId: string) =>
    deleteCard(cardId),
  moveCard: (cardId: string, toColumn: number) =>
    moveCard(cardId, { stage: toColumn, position: 0 }),
  getCompetitorVideos: () =>
    getCompetitorVideos(),
  getOwnAnalytics: (channelId?: string) =>
    getOwnAnalytics(channelId),
  repurposeVideo: (body: { title: string; video_id: string; channel: string; views: number }) =>
    repurposeVideo(body),
  getKnowledgeBase: () =>
    getKnowledgeBase(),
};
