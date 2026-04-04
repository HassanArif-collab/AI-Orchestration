#!/bin/bash
# FreeRouter v3 startup script
# Usage: ./start.sh

set -e

# Check for .env file
if [[ ! -f .env ]]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    if [[ -f .env.example ]]; then
        cp .env.example .env
        echo "Created .env from .env.example"
        echo "Please edit .env and add your API keys (OPENROUTER_API_KEY, GROQ_API_KEY)."
    fi
fi

echo ""
echo "Starting FreeRouter v3..."
echo ""
echo "Endpoints:"
echo "  API:    http://localhost:4000/v1"
echo "  Models: http://localhost:4000/v1/models"
echo "  Health: http://localhost:4000/health"
echo ""

exec python3 -m freerouter
