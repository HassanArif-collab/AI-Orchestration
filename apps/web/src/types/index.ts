// apps/web/src/types/index.ts
//
// UI-only types and display constants.
// Ground truth DB types are in @/lib/schema.ts (Zod schemas).
// This file re-exports them for convenience and adds UI-only types.

// ─── Re-export ground truth types from Zod schemas ───────────────────────
export type { KanbanCard, AgentThought, IterationLog } from '@/lib/schema';

// ─── UI Display Constants ────────────────────────────────────────────────

/** Maps column_index number to display name and description */
export const COLUMNS_DEF: Record<number, ColumnDef> = {
  1: { name: 'Topic Finding',      description: 'AI is searching for ideas',  color: 'blue'   },
  2: { name: 'Suggested Topics',   description: 'Approve within 3 hours',     color: 'yellow' },
  3: { name: 'Researching',        description: 'Deep research in progress',  color: 'green'  },
  4: { name: 'Script Evolution',   description: 'Drafting & Karpathy loop',   color: 'purple' },
  5: { name: 'Review + Visuals',   description: 'Waiting for your approval',  color: 'orange' },
  6: { name: 'Published (Notion)', description: 'Done!',                      color: 'emerald'},
};

export interface ColumnDef {
  name: string;
  description: string;
  color: string;
}

// ─── Agent Display Config ────────────────────────────────────────────────

/** Agent name display configuration (used by AgentLog component) */
export const AGENT_DISPLAY: Record<string, { label: string; emoji: string; colorClass: string }> = {
  topic_finder:     { label: 'Topic Finder',     emoji: '🔵', colorClass: 'text-[hsl(var(--brand-300))]' },
  researcher:       { label: 'Researcher',       emoji: '🟢', colorClass: 'text-[hsl(var(--lineage-emerald))]' },
  script_writer:    { label: 'Script Writer',    emoji: '🟣', colorClass: 'text-[hsl(var(--lineage-indigo))]' },
  scorer:           { label: 'Scorer',           emoji: '🟠', colorClass: 'text-[hsl(var(--lineage-amber))]' },
  challenger:       { label: 'Challenger',       emoji: '🔴', colorClass: 'text-[hsl(var(--lineage-rose))]' },
  visual_annotator: { label: 'Visual Annotator', emoji: '🔷', colorClass: 'text-[hsl(var(--lineage-cyan))]' },
  system:           { label: 'System',           emoji: '⚙️', colorClass: 'text-[hsl(var(--neutral-400))]' },
};

// ─── Thought Type Display Config ─────────────────────────────────────────

export const THOUGHT_DISPLAY: Record<string, { emoji: string; colorClass: string }> = {
  thinking:     { emoji: '🧠', colorClass: 'text-blue-400'   },
  search:       { emoji: '🔍', colorClass: 'text-green-400'  },
  output:       { emoji: '✍️', colorClass: 'text-purple-400' },
  error:        { emoji: '🚨', colorClass: 'text-red-400'    },
  memory_read:  { emoji: '💾', colorClass: 'text-yellow-400' },
  memory_write: { emoji: '💾', colorClass: 'text-yellow-400' },
};

// ─── UI-Only Types (not from DB) ────────────────────────────────────────

/** Card action types for the UI */
export type CardAction = 'save' | 'start_pipeline' | 'resubmit' | 'review' | 'none';

export interface CardActionInfo {
  action: CardAction;
  reason: string;
  label: string;
  variant: 'primary' | 'secondary' | 'warning' | 'success';
}

// ─── Model Registry (display only) ───────────────────────────────────────

export const MODEL_REGISTRY: { agent: string; model: string; provider: string; reason: string }[] = [
  { agent: 'Researcher',       model: 'gemini-1.5-pro',          provider: 'OpenRouter', reason: '1M token context for massive research docs'   },
  { agent: 'Script Writer',    model: 'llama-3.3-70b-versatile', provider: 'Groq',       reason: 'Fast inference for creative writing'          },
  { agent: 'Scorer',           model: 'llama-3.3-70b-versatile', provider: 'Groq',       reason: 'Speed for 20-iteration loop'                  },
  { agent: 'Challenger',       model: 'llama-3.3-70b-versatile', provider: 'Groq',       reason: 'Fast mutation generation'                     },
  { agent: 'Visual Annotator', model: 'llama3.2',                provider: 'Ollama',     reason: 'Simple task, save cloud tokens'               },
  { agent: 'Topic Finder',     model: 'gemini-2.0-flash',        provider: 'OpenRouter', reason: 'Fast + cheap for viability grading'            },
];

// ─── Pipeline State (from LangGraph API response) ────────────────────────

export interface PipelineStateResponse {
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
}

// ─── Health Check Types ──────────────────────────────────────────────────

export interface HealthServicesResponse {
  critical: Record<string, boolean>;
  optional: Record<string, boolean>;
  missing_critical: string[];
  missing_optional: string[];
}

// ─── DLQ Types ───────────────────────────────────────────────────────────

export interface DLQItem {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  error_message: string;
  status: string;
  created_at: string;
  retries: number;
}
