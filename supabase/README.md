# Supabase Setup

## 1. Create a Supabase Project
Go to https://supabase.com/dashboard and create a free project.

## 2. Run the Migrations

### Initial Schema
- Go to SQL Editor in your Supabase dashboard
- Click "New Query"
- Paste the contents of `migrations/001_initial_schema.sql`
- Click "Run"

### Research Cache (Phase 2B)
- Run `migrations/002_research_cache.sql` in the Supabase SQL Editor
- This creates the permanent research cache table

## 3. Get Your Keys
Go to Settings → API and copy:
- **Project URL** → `SUPABASE_URL` in your `.env`
- **anon / public key** → `SUPABASE_ANON_KEY` in your `.env`
- **service_role key** → `SUPABASE_SERVICE_ROLE_KEY` in your `.env`

## 4. Verify Realtime
Go to Database → Replication and confirm that `agent_thoughts`,
`kanban_cards`, `pipeline_runs`, and `research_cache` are listed under the
`supabase_realtime` publication.

## Tables

### agent_thoughts (Phase 1)
Stores agent progress updates for the Kanban card drawer.

### research_cache (Phase 2B)
Stores every research dossier permanently for instant reuse.
