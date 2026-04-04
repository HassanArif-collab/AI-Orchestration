# Supabase Setup for AI-Orchestration

This document describes the required Supabase configuration for the AI-Orchestration Content Factory pipeline.

## Required Tables

### 1. `kanban_cards`

Stores the pipeline cards that move through the 6-column Kanban board.

```sql
CREATE TABLE kanban_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_brief JSONB NOT NULL,
    column INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'discovering',
    viability_score INTEGER,
    error_message TEXT,
    expires_at TIMESTAMPTZ,  -- For Column 2 cards (3-hour timer)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kanban_cards_column ON kanban_cards(column);
CREATE INDEX idx_kanban_cards_status ON kanban_cards(status);
CREATE INDEX idx_kanban_cards_expires ON kanban_cards(expires_at) WHERE expires_at IS NOT NULL;
```

### 2. `agent_thoughts`

Stores real-time agent thinking updates for WebSocket streaming.

```sql
CREATE TABLE agent_thoughts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID NOT NULL REFERENCES kanban_cards(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    thought_type TEXT NOT NULL DEFAULT 'info',
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_agent_thoughts_card ON agent_thoughts(card_id);
CREATE INDEX idx_agent_thoughts_created ON agent_thoughts(created_at DESC);
```

### 3. `research_dossiers`

Stores cached research results for reuse across pipeline runs.

```sql
CREATE TABLE research_dossiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_hash TEXT NOT NULL UNIQUE,
    topic TEXT NOT NULL,
    dossier JSONB NOT NULL,
    sources JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_research_dossiers_hash ON research_dossiers(topic_hash);
```

### 4. `pipeline_runs` (LangGraph Checkpoints)

Stores LangGraph state snapshots for crash recovery.

```sql
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id TEXT NOT NULL UNIQUE,
    checkpoint JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pipeline_runs_thread ON pipeline_runs(thread_id);
```

## Realtime Configuration

Enable realtime on tables that the frontend subscribes to:

1. Go to Supabase Dashboard → Database → Replication
2. Enable realtime for:
   - `kanban_cards`
   - `agent_thoughts`

## Row Level Security (RLS) Policies

If RLS is enabled (default), add policies for the anon key:

```sql
-- Allow anon key to read/write kanban_cards
CREATE POLICY "Allow anon read" ON kanban_cards
    FOR SELECT USING (true);
CREATE POLICY "Allow anon insert" ON kanban_cards
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anon update" ON kanban_cards
    FOR UPDATE USING (true);
CREATE POLICY "Allow anon delete" ON kanban_cards
    FOR DELETE USING (true);

-- Allow anon key to read/write agent_thoughts
CREATE POLICY "Allow anon read" ON agent_thoughts
    FOR SELECT USING (true);
CREATE POLICY "Allow anon insert" ON agent_thoughts
    FOR INSERT WITH CHECK (true);
```

## Environment Variables

Add these to your `.env` file:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key  # For backend admin operations
```

For the React frontend (`apps/web/.env`):

```bash
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_URL=http://localhost:3000
```

## Connection Modes

Supabase provides two connection modes:

1. **Transaction mode** (port 6543): For serverless functions, auto-scaling
2. **Session mode** (port 5432): For persistent connections, required for LangGraph checkpointer

The LangGraph checkpointer uses session mode for proper transaction handling.

## Verification

After setup, verify the connection:

```python
from packages.core.supabase_client import get_supabase

sb = get_supabase()
result = sb.table("kanban_cards").select("count").execute()
print(f"Total cards: {result.data}")
```
