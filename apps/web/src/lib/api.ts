import type { DiscoverRequest, ResumeRequest, PipelineStateResponse, QuotaResponse } from '../types';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }

  return res.json();
}

// ── Pipeline Endpoints ──

export const api = {
  // Trigger topic discovery
  discover: (body: DiscoverRequest) =>
    request<{ status: string; card_id: string }>('/api/v1/pipeline/discover', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // Start production pipeline for a card
  produce: (cardId: string) =>
    request<{ status: string; card_id: string }>(`/api/v1/pipeline/produce/${cardId}`, {
      method: 'POST',
    }),

  // Resume after human review
  resume: (cardId: string, decision: ResumeRequest) =>
    request<{ status: string }>(`/api/v1/pipeline/langgraph/resume/${cardId}`, {
      method: 'POST',
      body: JSON.stringify(decision),
    }),

  // Get current LangGraph state
  getPipelineState: (cardId: string) =>
    request<PipelineStateResponse>(`/api/v1/pipeline/langgraph/state/${cardId}`),

  // Get live provider quotas
  getQuota: () =>
    request<QuotaResponse>('/api/v1/providers/quota'),

  // Get skill file contents (for System Editor)
  getSkills: () =>
    request<{ files: { name: string; content: string }[] }>('/api/v1/settings/skills'),

  // Save a suggested topic (prevents 3-hour auto-delete)
  saveCard: (cardId: string) =>
    request<{ status: string }>(`/api/v1/kanban/cards/${cardId}/save`, {
      method: 'POST',
    }),

  // Delete an expired/unwanted card
  deleteCard: (cardId: string) =>
    request<{ status: string }>(`/api/v1/kanban/tasks/${cardId}`, {
      method: 'DELETE',
    }),

  // Move card between columns (for drag-and-drop)
  moveCard: (cardId: string, toColumn: number) =>
    request<{ status: string }>(`/api/v1/kanban/tasks/${cardId}`, {
      method: 'PATCH',
      body: JSON.stringify({ stage: toColumn }),
    }),

  // Get all kanban tasks
  getTasks: () =>
    request<{ tasks: unknown[] }>('/api/v1/kanban/tasks'),

  // Get kanban stats
  getStats: () =>
    request<{ total_tasks: number; by_stage: Record<number, number>; by_status: Record<string, number> }>('/api/v1/kanban/stats'),
};
