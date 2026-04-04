-- 001_initial_schema.sql
-- All tables for the AI Orchestration pipeline (replaces SQLite *.db files).

-- ─── Kanban Cards ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kanban_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL DEFAULT '',
    column_index INTEGER NOT NULL DEFAULT 1 CHECK (column_index BETWEEN 1 AND 6),
    pipeline_run_id TEXT,
    parent_id UUID REFERENCES kanban_cards(id),
    color TEXT NOT NULL DEFAULT '#1D9E75',
    metadata JSONB DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'idle',
    position INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Agent Thoughts ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_thoughts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES kanban_cards(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL DEFAULT 'unknown',
    thought_type TEXT NOT NULL DEFAULT 'thinking'
        CHECK (thought_type IN ('thinking','search','output','error','memory_read','memory_write')),
    content TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_thoughts_card_id ON agent_thoughts(card_id);

-- ─── Pipeline Runs ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    current_stage TEXT NOT NULL DEFAULT 'trend_analysis',
    stage_outputs JSONB DEFAULT '{}'::jsonb,
    stage_status JSONB DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'running',
    error_message TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Topic Briefs (Topic Reservoir) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS topic_briefs (
    brief_id TEXT PRIMARY KEY,
    topic_statement TEXT NOT NULL,
    big_question TEXT DEFAULT '',
    genre_id TEXT DEFAULT '',
    gap_type TEXT DEFAULT '',
    viability_score_breakdown JSONB DEFAULT '{}'::jsonb,
    anchor_candidates TEXT[] DEFAULT '{}',
    mainstream_assumption TEXT DEFAULT '',
    urgency_flag BOOLEAN DEFAULT FALSE,
    timing_rationale TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'reservoir',
    content_type TEXT DEFAULT 'original',
    adaptation_source_video_id TEXT,
    structural_reference_video_id TEXT,
    structural_reference_id TEXT
);

-- ─── Video Performance ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS video_performance (
    video_id TEXT PRIMARY KEY,
    publication_date TIMESTAMPTZ,
    genre_id TEXT DEFAULT '',
    topic_statement TEXT DEFAULT '',
    viability_score_at_selection REAL DEFAULT 0,
    engagement_24h REAL,
    engagement_7d REAL,
    engagement_30d REAL,
    engagement_90d REAL,
    retention_curve_shape TEXT,
    anchor_bridge_correlation JSONB,
    topic_resonance_score REAL
);

-- ─── Production Cycles ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS production_cycles (
    cycle_id TEXT PRIMARY KEY,
    topic_statement TEXT DEFAULT '',
    genre TEXT DEFAULT '',
    source TEXT DEFAULT 'topic_finder',
    current_phase TEXT NOT NULL DEFAULT 'topic_selected',
    status TEXT NOT NULL DEFAULT 'active',
    current_baseline_score REAL DEFAULT 0,
    experiment_iterations INTEGER DEFAULT 0,
    music_architecture_id TEXT,
    published_video_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lock_expires_at TIMESTAMPTZ,
    pipeline_run_id TEXT
);

-- ─── Escalations ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS escalations (
    escalation_id TEXT PRIMARY KEY,
    cycle_id TEXT,
    type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',
    context_payload JSONB DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','approved','rejected','modified')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Iteration Logs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS iteration_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    score REAL NOT NULL,
    previous_score REAL NOT NULL,
    beat_baseline BOOLEAN NOT NULL DEFAULT FALSE,
    mutation_zone TEXT NOT NULL DEFAULT '',
    script_json JSONB,
    failed_questions JSONB DEFAULT '[]'::jsonb,
    fixed_questions JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_iteration_logs_run_id ON iteration_logs(run_id);

-- ─── Enable Row Level Security (best practice; anon key used server-side) ────
ALTER TABLE kanban_cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_thoughts ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE topic_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE production_cycles ENABLE ROW LEVEL SECURITY;
ALTER TABLE escalations ENABLE ROW LEVEL SECURITY;
ALTER TABLE iteration_logs ENABLE ROW LEVEL SECURITY;

-- Permissive policies for service-side access (anon key)
CREATE POLICY "anon_all_kanban_cards" ON kanban_cards FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_agent_thoughts" ON agent_thoughts FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_pipeline_runs" ON pipeline_runs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_topic_briefs" ON topic_briefs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_video_performance" ON video_performance FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_production_cycles" ON production_cycles FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_escalations" ON escalations FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "anon_all_iteration_logs" ON iteration_logs FOR ALL USING (true) WITH CHECK (true);

-- ─── Updated At Trigger ──────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_kanban_cards_updated_at BEFORE UPDATE ON kanban_cards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_pipeline_runs_updated_at BEFORE UPDATE ON pipeline_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_production_cycles_updated_at BEFORE UPDATE ON production_cycles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
