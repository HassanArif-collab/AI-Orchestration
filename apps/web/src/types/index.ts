// ============================================================
// KANBAN TYPES
// ============================================================

export interface KanbanCard {
  id: string;
  topic_brief: TopicBrief | null;
  column: number;                    // 1-6
  status: PipelineStatus;
  viability_score: number | null;
  error_message: string | null;
  expires_at: string | null;         // ISO timestamp, only for Column 2
  created_at: string;
  updated_at: string;
}

export interface TopicBrief {
  title: string;
  description: string;
  angle: string;
  score?: number;
  question_results?: ViabilityQuestion[];
}

export interface ViabilityQuestion {
  question: string;
  passed: boolean;
  reasoning: string;
}

export type PipelineStatus =
  | "discovering"
  | "grading"
  | "suggested"
  | "researching"
  | "drafting"
  | "scoring"
  | "mutating"
  | "visuals"
  | "review"
  | "publishing"
  | "complete"
  | "error";

// Maps column number to display name and description
export const COLUMNS: Record<number, ColumnDef> = {
  1: { name: "Topic Finding",       description: "AI is searching for ideas",     color: "blue"   },
  2: { name: "Suggested Topics",    description: "Approve within 3 hours",        color: "yellow" },
  3: { name: "Researching",         description: "Deep research in progress",     color: "green"  },
  4: { name: "Script Evolution",    description: "Drafting & Karpathy loop",      color: "purple" },
  5: { name: "Review + Visuals",    description: "Waiting for your approval",     color: "orange" },
  6: { name: "Published (Notion)",  description: "Done!",                         color: "emerald"},
};

export interface ColumnDef {
  name: string;
  description: string;
  color: string;
}

// ============================================================
// AGENT THOUGHT TYPES
// ============================================================

export interface AgentThought {
  id: string;
  card_id: string;
  agent_name: AgentName;
  thought: string;
  thought_type: ThoughtType;
  color: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export type AgentName =
  | "topic_finder"
  | "researcher"
  | "script_writer"
  | "scorer"
  | "challenger"
  | "visual_annotator"
  | "system";

export type ThoughtType =
  | "info"
  | "thinking"
  | "error"
  | "success"
  | "milestone";

// Display config for each agent (used by AgentLog component)
export const AGENT_DISPLAY: Record<AgentName, { label: string; emoji: string; colorClass: string }> = {
  topic_finder:     { label: "Topic Finder",     emoji: "🔵", colorClass: "text-agent-topic"      },
  researcher:       { label: "Researcher",       emoji: "🟢", colorClass: "text-agent-researcher"  },
  script_writer:    { label: "Script Writer",    emoji: "🟣", colorClass: "text-agent-writer"      },
  scorer:           { label: "Scorer",           emoji: "🟠", colorClass: "text-agent-scorer"      },
  challenger:       { label: "Challenger",       emoji: "🔴", colorClass: "text-agent-challenger"  },
  visual_annotator: { label: "Visual Annotator", emoji: "🔷", colorClass: "text-agent-visual"     },
  system:           { label: "System",           emoji: "⚙️", colorClass: "text-agent-system"     },
};

// ============================================================
// QUOTA / TELEMETRY TYPES
// ============================================================

export interface ProviderQuota {
  name: string;             // "groq", "openrouter", "ollama"
  rpm_remaining: number;    // -1 means unlimited/unknown
  tpm_remaining: number;
  last_updated: string;
}

export interface QuotaResponse {
  providers: ProviderQuota[];
}

// ============================================================
// PIPELINE STATE TYPES (mirrors LangGraph ProductionState)
// ============================================================

export interface PipelineStateResponse {
  card_id: string;
  values: {
    evaluation_score: number;
    best_score: number;
    iteration_count: number;
    pipeline_status: PipelineStatus;
    current_draft: string;
    visual_plan: string;
    error: string | null;
  };
  next: string[];   // Which node runs next (empty = complete or interrupted)
}

// ============================================================
// API REQUEST/RESPONSE TYPES
// ============================================================

export interface DiscoverRequest {
  seed_hint?: string;
}

export interface ResumeRequest {
  approved: boolean;
  feedback?: string;
}

// ============================================================
// MODEL REGISTRY (from Phase 3 — display only)
// ============================================================

export const MODEL_REGISTRY: { agent: string; model: string; provider: string; reason: string }[] = [
  { agent: "Researcher",       model: "gemini-1.5-pro",         provider: "OpenRouter", reason: "1M token context for massive research docs"   },
  { agent: "Script Writer",    model: "llama-3.3-70b-versatile", provider: "Groq",       reason: "Fast inference for creative writing"          },
  { agent: "Scorer",           model: "llama-3.3-70b-versatile", provider: "Groq",       reason: "Speed for 20-iteration loop"                  },
  { agent: "Challenger",       model: "llama-3.3-70b-versatile", provider: "Groq",       reason: "Fast mutation generation"                     },
  { agent: "Visual Annotator", model: "llama3.2",                provider: "Ollama",     reason: "Simple task, save cloud tokens"               },
  { agent: "Topic Finder",     model: "gemini-2.0-flash",        provider: "OpenRouter", reason: "Fast + cheap for viability grading"            },
];
