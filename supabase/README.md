# Supabase Setup

## 1. Create a Supabase Project
Go to https://supabase.com/dashboard and create a free project.

## 2. Run the Migration
- Go to SQL Editor in your Supabase dashboard
- Click "New Query"
- Paste the contents of `migrations/001_initial_schema.sql`
- Click "Run"

## 3. Get Your Keys
Go to Settings → API and copy:
- **Project URL** → `SUPABASE_URL` in your `.env`
- **anon / public key** → `SUPABASE_ANON_KEY` in your `.env`
- **service_role key** → `SUPABASE_SERVICE_ROLE_KEY` in your `.env`

## 4. Verify Realtime
Go to Database → Replication and confirm that `agent_thoughts`,
`kanban_cards`, and `pipeline_runs` are listed under the
`supabase_realtime` publication.
