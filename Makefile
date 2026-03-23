.PHONY: install test lint format freerouter freerouter-web

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
