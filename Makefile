.PHONY: install test lint format freerouter freerouter-web frontend-install frontend-dev frontend-build frontend-preview frontend-lint

install:
        pip install -e ".[all]"

test:
        pytest tests/ -v

lint:
        ruff check packages/ tests/

format:
        ruff format packages/ tests/

# ─── FreeRouter ──────────────────────────────────────────────────────────────
# FreeRouter MUST be running before any pipeline LLM calls work.
# It reads API keys from freerouter/.env (managed via http://localhost:8080)

freerouter:
        @echo "Starting FreeRouter proxy on :4000 ..."
        @echo "Ensure freerouter/.env has your GROQ_API_KEY / OPENROUTER_API_KEY"
        cd freerouter && python -m freerouter proxy

freerouter-web:
        @echo "Starting FreeRouter web dashboard on :8080 ..."
        cd freerouter && python -m freerouter web

# Run both FreeRouter servers (requires two terminals — this shows the commands)
freerouter-all:
        @echo "Run these in two separate terminals:"
        @echo "  Terminal 1: make freerouter-web"
        @echo "  Terminal 2: make freerouter"

# ─── Frontend (Phase 5) ─────────────────────────────────────────────────────────
# React + Vite + Tailwind frontend for the Content Factory dashboard

frontend-install:
        @echo "Installing frontend dependencies..."
        cd apps/web && npm install

frontend-dev:
        @echo "Starting Vite dev server on :5173..."
        cd apps/web && npm run dev

frontend-build:
        @echo "Building frontend for production..."
        cd apps/web && npm run build

frontend-preview:
        @echo "Previewing production build..."
        cd apps/web && npm run preview

frontend-lint:
        @echo "Type-checking frontend..."
        cd apps/web && npx tsc --noEmit
