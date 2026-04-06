// apps/web/src/lib/schema.ts
// Ground Truth Zod Schemas — must match supabase/migrations/001_initial_schema.sql exactly.
// These are the single source of truth for all frontend types.

import { z } from 'zod';

// ─── Kanban Card Schema (kanban_cards table) ──────────────────────────────

/**
 * CRITICAL RULES:
 * - Column position is `column_index` (Integer 1-6), NOT `column` (String).
 * - Cards use `parent_id` for lineage (sub-tasks point to parents).
 * - `topic_brief` and `viability_score` do NOT exist at root level;
 *   they live inside the `metadata` JSONB column.
 */
export const KanbanCardSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  column_index: z.number().int().min(1).max(6),
  position: z.number().int(),
  status: z.enum(['idle', 'processing', 'error', 'review_required', 'completed']),
  pipeline_run_id: z.string().nullable().optional(),
  parent_id: z.string().uuid().nullable().optional(), // Lineage key
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/),
  metadata: z.record(z.string(), z.unknown()).default({}), // topic_brief lives here!
  expires_at: z.string().datetime({ offset: true }).nullable().optional(),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});

export type KanbanCard = z.infer<typeof KanbanCardSchema>;

// ─── Agent Thought Schema (agent_thoughts table) ──────────────────────────

/**
 * Used for the live activity feed.
 * `thought_type` constraint matches the DB CHECK constraint exactly.
 * Note: field is `content` (not `thought`), matching the DB column name.
 */
export const AgentThoughtSchema = z.object({
  id: z.string().uuid(),
  card_id: z.string().uuid(),
  agent_name: z.string(),
  thought_type: z.enum(['thinking', 'search', 'output', 'error', 'memory_read', 'memory_write']),
  content: z.string(),
  created_at: z.string().datetime({ offset: true }),
});

export type AgentThought = z.infer<typeof AgentThoughtSchema>;

// ─── Iteration Log Schema (iteration_logs table) ──────────────────────────

/**
 * Used for the Karpathy Loop visualizer.
 * `script_json` is JSONB containing hook, anchor, and full_text.
 */
export const IterationLogSchema = z.object({
  id: z.string().uuid(),
  run_id: z.string(),
  iteration: z.number().int(),
  score: z.number(),
  previous_score: z.number(),
  beat_baseline: z.boolean(),
  mutation_zone: z.string(),
  script_json: z.object({
    hook: z.string().optional(),
    anchor: z.string().optional(),
    full_text: z.string(),
  }),
  failed_questions: z.array(z.string()),
  fixed_questions: z.array(z.string()),
  created_at: z.string().datetime({ offset: true }),
});

export type IterationLog = z.infer<typeof IterationLogSchema>;
