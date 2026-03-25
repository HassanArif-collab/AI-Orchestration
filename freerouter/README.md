# FreeRouter

> **Smart LLM Proxy that always prefers free models**

FreeRouter is an intelligent LLM proxy built on [LiteLLM](https://github.com/BerriAI/litellm) that automatically routes requests to the best available **free** model based on the task type. It provides a single OpenAI-compatible API endpoint, making it work seamlessly with any tool that supports OpenAI's API.

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Your App      │────▶│  FreeRouter  │────▶│  Best Free Model│
│  (Cursor, etc) │     │  (localhost) │     │  (Auto-selected)│
└─────────────────┘     └──────────────┘     └─────────────────┘
```

## ✨ Features

- **🔒 Always Free First** - Prioritizes completely free models (local Ollama, OpenRouter free tier, Groq free tier)
- **🧠 Task-Based Routing** - Automatically detects task type and selects the best model
- **🔄 Intelligent Fallbacks** - If one provider fails, automatically tries the next
- **🔍 Web Search Interception** - Detects web search requests and executes them automatically
- **🏥 Health Monitoring** - Periodically checks model availability and adjusts routing
- **🔌 OpenAI-Compatible** - Works with Cursor, Claude Code, Continue, LangChain, and more
- **📊 Cost Tracking** - Monitor your usage and costs
- **⚡ Fast Classification** - Uses lightweight models for quick routing decisions
- **🐳 One-Command Deploy** - Docker Compose for instant setup

## 📋 Task Categories

FreeRouter automatically classifies your request and routes to the optimal model:

| Category | Description | Best Model |
|----------|-------------|------------|
| `simple_chat` | General conversation, questions | Groq Llama-3.3-70B / Qwen 2.5 7B |
| `coding` | Writing, debugging code | Qwen 2.5 Coder 32B / DeepSeek |
| `reasoning` | Complex analysis, math | DeepSeek R1 (Free) |
| `agentic` | Multi-step, tool use | Qwen 2.5 32B / Llama 3.3 70B |
| `vision` | Image understanding | Llama 3.2 Vision / Qwen VL |
| `long_context` | Large documents | Qwen 2.5 32B (32k context) |

## 🚀 Quick Start

> **See [USAGE.md](USAGE.md) for the complete usage guide.**

### Prerequisites

- Python 3.10+ or Docker
- [Ollama](https://ollama.ai) (optional, for local models)
- API keys for cloud providers (OpenRouter, Groq)

### Quick Start Script

```bash
# Run the quick start script for guided setup
python quickstart.py
```

### Installation

#### Option 1: pip (Recommended)

```bash
# Clone the repository
git clone https://github.com/freerouter/freerouter.git
cd freerouter

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Copy environment file
cp .env.example .env

# Edit .env and add your API keys
# OPENROUTER_API_KEY=your_key_here
# GROQ_API_KEY=your_key_here
```

#### Option 2: Docker

```bash
# Clone and enter directory
git clone https://github.com/freerouter/freerouter.git
cd freerouter

# Copy environment file and add your keys
cp .env.example .env
# Edit .env with your API keys

# Start with Docker Compose
docker-compose up -d
```

### Starting the Server

```bash
# Start FreeRouter
freerouter start

# Or with custom options
freerouter start --host 0.0.0.0 --port 4000 --config ./config/proxy_server_config.yaml

# Check environment configuration
freerouter env

# View model aliases
freerouter config
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file with your API keys:

```bash
# Required for full functionality
OPENROUTER_API_KEY=your_openrouter_key
GROQ_API_KEY=your_groq_key

# Optional
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
```

### Model Aliases

Use these aliases in your applications:

| Alias | Description |
|-------|-------------|
| `free-router/fast` | Fast responses, simple chat |
| `free-router/coder` | Code generation and debugging |
| `free-router/reasoning` | Complex reasoning tasks |
| `free-router/smart` | Balanced intelligence |
| `free-router/vision` | Image understanding |
| `free-router/long-context` | Large document processing |
| `free-router/balanced` | Default, general purpose |
| `free-router/auto` | **Auto-routing - classifies task automatically** |

### Auto-Routing

Use `free-router/auto` to let FreeRouter automatically classify your request and route to the best model:

```python
response = client.chat.completions.create(
    model="free-router/auto",  # Automatically selects best model
    messages=[
        {"role": "user", "content": "Write a Python function to sort a list"}
    ]
)
# Routes to free-router/coder automatically

response = client.chat.completions.create(
    model="free-router/auto",
    messages=[
        {"role": "user", "content": "What is quantum entanglement?"}
    ]
)
# Routes to free-router/fast or free-router/smart based on complexity
```

### Web Search Interception

FreeRouter can intercept web search tool calls and execute them automatically:

```python
# Tool calls for web_search, search, google_search are intercepted
response = client.chat.completions.create(
    model="free-router/smart",
    messages=[
        {"role": "user", "content": "Search for the latest AI news"}
    ],
    tools=[{
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        }
    }]
)
# FreeRouter executes the search and injects results automatically
```

## 🛠️ Using with Applications

### Claude Code

Set environment variables before running Claude Code:

```bash
# In your shell or .bashrc/.zshrc
export ANTHROPIC_BASE_URL=http://localhost:4000
export ANTHROPIC_API_KEY=any_key  # FreeRouter doesn't require this by default

# Now run Claude Code
claude-code
```

### Cursor

1. Open Cursor Settings (Ctrl/Cmd + ,)
2. Navigate to **Models**
3. Set **OpenAI API Base URL** to: `http://localhost:4000/v1`
4. Set **OpenAI API Key** to: `any_key` (or your FreeRouter API key if configured)
5. Select model: `free-router/smart` or any other alias

### Continue

Add to your `config.json`:

```json
{
  "models": [
    {
      "title": "FreeRouter Smart",
      "provider": "openai",
      "model": "free-router/smart",
      "apiBase": "http://localhost:4000/v1",
      "apiKey": "any_key"
    }
  ]
}
```

### LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="free-router/smart",
    base_url="http://localhost:4000/v1",
    api_key="any_key"
)

response = llm.invoke("Explain quantum computing")
print(response.content)
```

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="any_key"
)

response = client.chat.completions.create(
    model="free-router/coder",
    messages=[
        {"role": "user", "content": "Write a Python function to sort a list"}
    ]
)

print(response.choices[0].message.content)
```

### cURL

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer any_key" \
  -d '{
    "model": "free-router/smart",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## 🏥 Health Check

Check if FreeRouter is running and view provider status:

```bash
curl http://localhost:4000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "providers": {
    "ollama": {"status": "healthy", "latency_ms": 15.2},
    "groq": {"status": "healthy", "latency_ms": 120.5},
    "openrouter": {"status": "degraded", "latency_ms": 250.0}
  }
}
```

Detailed status:
```bash
curl http://localhost:4000/status
```

## 📊 Available Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /v1/models` | List available models |
| `POST /v1/chat/completions` | Chat completions |
| `POST /v1/completions` | Text completions |
| `POST /v1/embeddings` | Embeddings (if configured) |
| `GET /docs` | API documentation |

## 🏗️ Architecture

```
FreeRouter Architecture
├── src/freerouter/
│   ├── __init__.py          # Package initialization
│   ├── cli.py               # CLI commands (freerouter start, etc.)
│   ├── config.py            # Configuration management
│   ├── classifier.py        # Task classification logic
│   ├── proxy.py             # FastAPI proxy with routing
│   ├── websearch.py         # Web search interception
│   └── health.py            # Model health monitoring
├── config/
│   └── proxy_server_config.yaml  # LiteLLM configuration
├── tests/
│   └── test_freerouter.py   # Test suite
├── .env                     # Environment variables
├── pyproject.toml           # Python package config
├── Dockerfile               # Docker image definition
└── docker-compose.yml       # Docker Compose setup
```

### Components

| Component | Description |
|-----------|-------------|
| `classifier.py` | Classifies requests into task categories (coding, reasoning, vision, etc.) |
| `proxy.py` | FastAPI wrapper that handles routing and web search interception |
| `websearch.py` | Intercepts tool calls for web search and executes them via DuckDuckGo/SearXNG |
| `health.py` | Monitors model availability and adjusts fallback chains |
| `config.py` | Loads and validates configuration and environment |

## 🔄 Fallback Chain

When a model fails, FreeRouter automatically falls back:

```
Primary Model → Fallback 1 → Fallback 2 → ...
     ↓              ↓            ↓
  Local Ollama → Groq Free → OpenRouter Free
```

Example for `free-router/coder`:
1. `ollama/qwen2.5-coder:32b` (local, free)
2. `openrouter/deepseek/deepseek-chat:free` (free tier)
3. `openrouter/qwen/qwen-2.5-coder-32b-instruct:free` (free tier)
4. `groq/qwen-2.5-coder-32b` (free tier)

## 🐛 Troubleshooting

### Ollama not running

```bash
# Start Ollama
ollama serve

# Pull recommended models
ollama pull qwen2.5:7b
ollama pull qwen2.5-coder:32b
ollama pull llama3.2-vision:11b
```

### Connection refused

```bash
# Check if FreeRouter is running
curl http://localhost:4000/health

# Check logs
docker-compose logs -f freerouter
```

### API key errors

```bash
# Verify your environment
freerouter env

# Ensure .env file has valid keys
cat .env
```

### Port already in use

```bash
# Use a different port
freerouter start --port 4001
```

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

## 🙏 Acknowledgments

- [LiteLLM](https://github.com/BerriAI/litellm) - The foundation for this proxy
- [Ollama](https://ollama.ai) - Local LLM runtime
- [OpenRouter](https://openrouter.ai) - Free model access
- [Groq](https://groq.com) - Fast inference API

---

**Made with ❤️ by the FreeRouter Team**