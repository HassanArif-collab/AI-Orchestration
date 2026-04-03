# AI Content Factory — React Frontend

React + TypeScript + Vite frontend for the AI-Orchestration content production pipeline.

## Overview

This is the modern React frontend that replaces the legacy vanilla JS dashboard. It provides a real-time Kanban board view of pipeline progress, agent thinking streams, and content review tools.

## Tech Stack

- **React 19** + **TypeScript**
- **Vite** — build tool with HMR
- **Tailwind CSS v4** — utility-first styling
- **Supabase** — realtime database subscriptions
- **dnd-kit** — drag-and-drop for Kanban cards
- **SWR** — data fetching hooks

## Quick Start

```bash
cd apps/web

# Install dependencies
npm install

# Copy environment file
cp .env.example .env
# Edit .env: Add VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_URL

# Start dev server
npm run dev
```

Open **http://localhost:5173**

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_SUPABASE_URL` | Yes | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Yes | Supabase anon/public key |
| `VITE_API_URL` | Yes | Backend API URL (default: `http://localhost:3000`) |

## Project Structure

```
apps/web/src/
├── components/
│   ├── kanban/        ← Kanban board (Board, Column, Card, CardDrawer)
│   ├── review/        ← Content review (ScriptViewer, PublishConfirmModal)
│   ├── chat/          ← Chat panel (ChatPanel)
│   ├── telemetry/     ← LLM provider metrics (QuotaPanel)
│   └── common/        ← Shared UI (StatusBadge, ErrorCard)
├── hooks/             ← Custom React hooks (useAgentStream, useChat, useYouTube)
├── layout/            ← Page layout (MainLayout, Sidebar)
├── lib/               ← Utilities (api.ts, supabase.ts, cardHelpers.ts, constants.ts)
└── types/             ← TypeScript type definitions
```

## Key Features

- **Kanban Board**: Real-time card movement via Supabase subscriptions
- **Agent Stream**: Live agent thinking updates with deduplication
- **Content Review**: Dual-column script viewer with publish workflow
- **Chat**: SSE-based streaming chat with LLM providers
- **Responsive**: Mobile-aware layout with collapsible sidebar

## Available Scripts

```bash
npm run dev          # Start dev server
npm run build        # Production build
npm run preview      # Preview production build
npm run lint         # ESLint check
```

## Backend Dependency

This frontend requires the FastAPI backend running at `VITE_API_URL` (default: `http://localhost:3000`). See the root [README.md](../../README.md) for backend setup instructions.

## Documentation

See [PHASE6_IMPLEMENTATION_PLAN.md](./docs/PHASE6_IMPLEMENTATION_PLAN.md) for planned improvements and audit fixes.
