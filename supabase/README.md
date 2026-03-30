# Supabase Configuration

This directory contains Supabase-related configuration and migrations.

## Tables

### agent_thoughts (Phase 1)
Stores agent progress updates for the Kanban card drawer.

### research_cache (Phase 2B)
Stores every research dossier permanently for instant reuse.

## Migrations

### 001_initial.sql
Initial schema setup (if exists).

### 002_research_cache.sql
Run this in the Supabase SQL Editor to create the permanent research cache table.

```sql
-- Run the contents of migrations/002_research_cache.sql
```

## After Phase 2B
Run `migrations/002_research_cache.sql` in the Supabase SQL Editor.
All research is now stored permanently.
