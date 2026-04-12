-- ============================================================
-- Permanent Research Dossier Storage
-- ============================================================
-- Stores every research dossier forever (no expiration).
-- Provides instant cache hits on repeated topics to save API tokens.

CREATE TABLE research_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT UNIQUE NOT NULL,
    topic_statement TEXT NOT NULL,
    dossier JSONB NOT NULL,
    source_urls TEXT[] DEFAULT '{}',
    source_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    brief_id TEXT,                    -- optional for easier lookup
    video_id TEXT                     -- optional, link to final video
);

CREATE INDEX idx_research_cache_key ON research_cache(cache_key);
CREATE INDEX idx_research_cache_topic ON research_cache(topic_statement);
CREATE INDEX idx_research_cache_date ON research_cache(created_at);
