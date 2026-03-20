#!/bin/bash
# FreeRouter startup script
# Usage: ./start.sh [options]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
HOST="0.0.0.0"
PORT=4000
CONFIG="config/proxy_server_config.yaml"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            HOST="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -c|--config)
            CONFIG="$2"
            shift 2
            ;;
        --help)
            echo "Usage: ./start.sh [options]"
            echo ""
            echo "Options:"
            echo "  -h, --host      Host to bind to (default: 0.0.0.0)"
            echo "  -p, --port      Port to bind to (default: 4000)"
            echo "  -c, --config    Config file path (default: config/proxy_server_config.yaml)"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Print banner
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║   ███████╗██████╗ ██╗  ██╗███████╗                           ║"
echo "║   ██╔════╝██╔══██╗██║  ██║██╔════╝                           ║"
echo "║   █████╗  ██████╔╝███████║█████╗                             ║"
echo "║   ██╔══╝  ██╔══██╗██╔══██║██╔══╝                             ║"
echo "║   ██║     ██║  ██║██║  ██║███████╗                           ║"
echo "║   ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝                           ║"
echo "║                                                              ║"
echo "║   Smart LLM Proxy • Always Free First                       ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for .env file
if [[ ! -f .env ]]; then
    echo -e "${YELLOW}Warning: .env file not found. Copying from .env.example...${NC}"
    if [[ -f .env.example ]]; then
        cp .env.example .env
        echo -e "${YELLOW}Please edit .env and add your API keys.${NC}"
    fi
fi

# Check if Ollama is running
echo -e "${GREEN}Checking if Ollama is running...${NC}"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ollama is running${NC}"
else
    echo -e "${YELLOW}! Ollama is not running. Starting...${NC}"
    if command -v ollama &> /dev/null; then
        ollama serve &
        sleep 3
        echo -e "${GREEN}✓ Ollama started${NC}"
    else
        echo -e "${YELLOW}! Ollama not found. Install from https://ollama.ai for local models.${NC}"
    fi
fi

# Print startup info
echo ""
echo -e "${GREEN}Starting FreeRouter...${NC}"
echo -e "  Host: ${HOST}"
echo -e "  Port: ${PORT}"
echo -e "  Config: ${CONFIG}"
echo ""
echo -e "Endpoints:"
echo -e "  API: ${GREEN}http://localhost:${PORT}/v1${NC}"
echo -e "  Docs: ${GREEN}http://localhost:${PORT}/docs${NC}"
echo -e "  Health: ${GREEN}http://localhost:${PORT}/health${NC}"
echo ""

# Start the server
exec python -m litellm --config "$CONFIG" --host "$HOST" --port "$PORT"