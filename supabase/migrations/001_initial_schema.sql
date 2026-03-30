-- ============================================================
-- AI-Orchestration V2: Complete Supabase Schema
-- ============================================================
-- Run this in: Supabase Dashboard → SQL Editor → New Query → Paste → Run
-- Or via CLI: supabase db push
--
-- This replaces ALL SQLite tables from:
--   packages/data/pipeline.db (pipeline_runs, topic_reservoir,
--     video_performance, production_registry, human_escalations)
--   packages/data/agent_thoughts.db (agent_thoughts)
--   packages/data/iteration_logs.db (iteration_log)
-- ============================================================

-- 1. Kanban Board Cards
-- Replaces: the KanbanStore class (in apps/api/dependencies.py)
-- Each card represents one topic/video moving through 6 columns
CREATE TABLE kanban_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    column_index INTEGER NOT NULL CHECK (column_index BETWEEN 1 AND 6),
    -- Column mapping:
    -- 1 = Topic Finding (agent searching)
    -- 2 = Suggested Topics (awaiting human save/expire)
    -- 3 = Researching (auto-triggered)
    -- 4 = Script Writing & Evolution
    -- 5 = Script + Visual Cues
    -- 6 = Notion (Done)
    parent_id UUID REFERENCES kanban_cards(id) ON DELETE SET NULL,
    brief_id TEXT,               -- links to topic_briefs.brief_id
    pipeline_run_id TEXT,        -- links to pipeline_runs.run_id
    color TEXT DEFAULT '#3B82F6',
    position INTEGER DEFAULT 0,  -- ordering within a column
    status TEXT DEFAULT 'idle' CHECK (status IN
        ('idle', 'thinking', 'error', 'complete', 'waiting', 'paused')),
    metadata JSONB DEFAULT '{}', -- arbitrary key-value (seed_query, genre_id, etc.)
    expires_at TIMESTAMPTZ,      -- only for column 2 cards (3-hour auto-delete)
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Agent Thinking Logs
-- Replaces: ThoughtsStore in apps/api/routers/kanban_routes.py
-- Every row auto-pushes to frontend via Supabase Realtime
CREATE TABLE agent_thoughts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID NOT NULL REFERENCES kanban_cards(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    -- Valid: 'topic_finder','researcher','script_writer',
    --        'evaluator','challenger','visual_annotator','chat_assistant'
    thought_type TEXT NOT NULL CHECK (thought_type IN
        ('thinking','search','output','error','memory_read','memory_write')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Topic Briefs
-- Replaces: topic_reservoir table in TopicReservoirDB
--           (packages/content_factory/topic_finder/db.py)
CREATE TABLE topic_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_id TEXT UNIQUE NOT NULL,
    topic_statement TEXT NOT NULL,
    big_question TEXT NOT NULL,
    genre_id TEXT NOT NULL,
    gap_type TEXT NOT NULL,
    viability_score_breakdown JSONB NOT NULL,
    anchor_candidates TEXT[] NOT NULL,
    mainstream_assumption TEXT NOT NULL,
    urgency_flag BOOLEAN DEFAULT false,
    timing_rationale TEXT NOT NULL,
    status TEXT DEFAULT 'reservoir' CHECK (status IN
        ('reservoir', 'in_production', 'complete', 'expired')),
    content_type TEXT DEFAULT 'original' CHECK (content_type IN
        ('original', 'adaptation')),
    adaptation_source_video_id TEXT,
    structural_reference_video_id TEXT,
    structural_reference_id TEXT,  -- legacy: full SourceVideoRecord ref
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Pipeline Runs
-- Replaces: pipeline_runs table in RunStore
--           (packages/pipeline/state.py)
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT UNIQUE NOT NULL,
    card_id UUID REFERENCES kanban_cards(id),
    current_stage TEXT NOT NULL,
    stage_outputs JSONB DEFAULT '{}',
    stage_status JSONB DEFAULT '{}',
    status TEXT DEFAULT 'running' CHECK (status IN
        ('running', 'paused', 'complete', 'error', 'waiting_human')),
    error_message TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Production Cycles
-- Replaces: production_registry table in OrchestrationDB
--           (packages/content_factory/orchestration/db.py)
CREATE TABLE production_cycles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id TEXT UNIQUE NOT NULL,
    topic_statement TEXT NOT NULL,
    genre TEXT NOT NULL,
    source TEXT DEFAULT 'topic_finder' CHECK (source IN
        ('topic_finder', 'adaptation', 'manual')),
    current_phase TEXT DEFAULT 'topic_selected',
    status TEXT DEFAULT 'active' CHECK (status IN
        ('active', 'paused', 'completed', 'failed')),
    current_baseline_score REAL DEFAULT 0.0,
    experiment_iterations INTEGER DEFAULT 0,
    pipeline_run_id TEXT,
    music_architecture_id TEXT,
    published_video_id TEXT,
    lock_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 6. Human Escalations
-- Replaces: human_escalations table in OrchestrationDB
CREATE TABLE escalations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    escalation_id TEXT UNIQUE NOT NULL,
    cycle_id TEXT,
    type TEXT NOT NULL CHECK (type IN
        ('instruction_update','hard_failure','reservoir_low',
         'weekly_summary','sensitive_content')),
    severity TEXT NOT NULL CHECK (severity IN
        ('low','medium','high','critical')),
    context_payload JSONB DEFAULT '{}',
    status TEXT DEFAULT 'pending' CHECK (status IN
        ('pending','approved','rejected','modified')),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 7. Video Performance
-- Replaces: video_performance table in PerformanceDB
--           (packages/content_factory/topic_finder/db.py)
CREATE TABLE video_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id TEXT UNIQUE NOT NULL,
    publication_date TIMESTAMPTZ,
    genre_id TEXT,
    topic_statement TEXT,
    viability_score_at_selection REAL,
    engagement_24h REAL,
    engagement_7d REAL,
    engagement_30d REAL,
    engagement_90d REAL,
    retention_curve_shape TEXT CHECK (retention_curve_shape IN
        ('Harris-Pattern','Continuous Decline','Early Exit','Late Drop')
        OR retention_curve_shape IS NULL),
    anchor_bridge_correlation JSONB,
    topic_resonance_score REAL
);

-- 8. Iteration Logs (Evolution Loop)
-- Replaces: iteration_log table in IterationLogStore
--           (packages/pipeline/iteration_store.py)
CREATE TABLE iteration_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    score REAL NOT NULL,
    previous_score REAL NOT NULL,
    beat_baseline BOOLEAN NOT NULL,
    mutation_zone TEXT NOT NULL,
    script_json JSONB,
    failed_questions JSONB DEFAULT '[]',
    fixed_questions JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 9. LLM Usage Tracking (Phase 3 populates this)
CREATE TABLE llm_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_used INTEGER,
    tokens_remaining INTEGER,
    requests_remaining INTEGER,
    response_time_ms INTEGER,
    agent_name TEXT,
    card_id UUID REFERENCES kanban_cards(id),
    recorded_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_kanban_column ON kanban_cards(column_index);
CREATE INDEX idx_kanban_expires ON kanban_cards(expires_at)
    WHERE expires_at IS NOT NULL;
CREATE INDEX idx_kanban_status ON kanban_cards(status);
CREATE INDEX idx_thoughts_card ON agent_thoughts(card_id);
CREATE INDEX idx_thoughts_created ON agent_thoughts(created_at DESC);
CREATE INDEX idx_briefs_status ON topic_briefs(status);
CREATE INDEX idx_briefs_brief_id ON topic_briefs(brief_id);
CREATE INDEX idx_runs_status ON pipeline_runs(status);
CREATE INDEX idx_runs_card ON pipeline_runs(card_id);
CREATE INDEX idx_runs_run_id ON pipeline_runs(run_id);
CREATE INDEX idx_cycles_status ON production_cycles(status);
CREATE INDEX idx_cycles_cycle_id ON production_cycles(cycle_id);
CREATE INDEX idx_iteration_run ON iteration_logs(run_id);
CREATE INDEX idx_usage_recorded ON llm_usage(recorded_at DESC);
CREATE INDEX idx_usage_provider ON llm_usage(provider);
CREATE INDEX idx_perf_video ON video_performance(video_id);

-- ============================================================
-- Enable Supabase Realtime
-- ============================================================
-- These tables stream changes to connected WebSocket clients
ALTER PUBLICATION supabase_realtime ADD TABLE agent_thoughts;
ALTER PUBLICATION supabase_realtime ADD TABLE kanban_cards;
ALTER PUBLICATION supabase_realtime ADD TABLE pipeline_runs;
