.PHONY: install install-minimal install-langgraph install-full install-windows test lint format freerouter freerouter-web frontend-install frontend-dev frontend-build frontend-preview frontend-lint clean

# ============================================================
# Installation Commands
# ============================================================

# Default: Install everything (CrewAI + LangGraph)
install:
	@echo "Installing all dependencies (CrewAI + LangGraph)..."
	pip install -e ".[all]"

# Minimal installation (core only, no CrewAI/LangGraph)
install-minimal:
	@echo "Installing minimal dependencies (core only)..."
	pip install -e "."

# LangGraph only (recommended for most users)
install-langgraph:
	@echo "Installing with LangGraph (no CrewAI)..."
	pip install -e ".[dev,memory,youtube,notion,pipeline,langgraph-deps]"

# Full installation with CrewAI (may have conflicts on some systems)
install-full:
	@echo "Installing full dependencies (CrewAI + LangGraph)..."
	pip install -e ".[all]"

# Windows-specific installation
install-windows:
	@echo "Installing with Windows-specific settings..."
	pip install -r requirements-windows.txt
	pip install -e ".[dev,memory,youtube,notion,pipeline,langgraph-deps,crewai-deps]"

# Clean install (removes old packages first)
install-clean:
	@echo "Cleaning old installation..."
	pip uninstall -y ai-orchestration crewai langchain langchain-core langgraph litellm
	pip cache purge
	@echo "Installing fresh..."
	pip install -e ".[all]"

# ============================================================
# Testing & Linting
# ============================================================

test:
	pytest tests/ -v

lint:
	ruff check packages/ tests/

format:
	ruff format packages/ tests/

# ============================================================
# FreeRouter (LLM Proxy)
# ============================================================
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

# ============================================================
# Frontend (Phase 5)
# ============================================================
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

# ============================================================
# Utility Commands
# ============================================================

clean:
	@echo "Cleaning Python cache..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaning pip cache..."
	pip cache purge 2>/dev/null || true
	@echo "Done."

# Show dependency status
status:
	@echo "=== Python Version ==="
	python --version
	@echo "\n=== Installed Packages ==="
	@pip list | grep -E "crewai|langgraph|langchain|psycopg|pydantic" || pip list | findstr /i "crewai langgraph langchain psycopg pydantic"
	@echo "\n=== Checking CrewAI ==="
	@python -c "from crewai import Agent; print('CrewAI: OK')" 2>/dev/null || echo "CrewAI: NOT INSTALLED"
	@echo "\n=== Checking LangGraph ==="
	@python -c "from langgraph.graph import StateGraph; print('LangGraph: OK')" 2>/dev/null || echo "LangGraph: NOT INSTALLED"
	@echo "\n=== Checking psycopg ==="
	@python -c "from psycopg_pool import AsyncConnectionPool; print('psycopg: OK')" 2>/dev/null || echo "psycopg: NOT INSTALLED"
