# FreeRouter

> **LiteLLM-based task router — always free**

FreeRouter v3 is a slim OpenAI-compatible proxy built on [LiteLLM](https://github.com/BerriAI/litellm). Send a task name as the `model` field and FreeRouter resolves it to the best free model with automatic fallback.

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────────────┐
│  Your App    │────▶│   FreeRouter    │────▶│  openrouter/qwen/...:free│
│  (OpenAI SDK)│     │  localhost:4000 │     │  openrouter/google/...:free│
└──────────────┘     └─────────────────┘     └──────────────────────────┘
```

## Named Routes

| Route | Primary Model | Fallback |
|-------|--------------|----------|
| `auto` | openrouter/qwen/qwen3.6-plus:free | openrouter/meta-llama/llama-3.3-70b-instruct:free |
| `researcher` | openrouter/qwen/qwen3.6-plus:free | openrouter/meta-llama/llama-3.3-70b-instruct:free |
| `topic_finder` | openrouter/qwen/qwen3.6-plus:free | openrouter/meta-llama/llama-3.3-70b-instruct:free |
| `script_writer` | openrouter/qwen/qwen3.6-plus:free | openrouter/google/gemma-3-27b-it:free |
| `scorer` | openrouter/google/gemma-3-27b-it:free | openrouter/qwen/qwen3.6-plus:free |
| `challenger` | openrouter/qwen/qwen3.6-plus:free | openrouter/google/gemma-3-27b-it:free |
| `annotator` | openrouter/google/gemma-3-27b-it:free | openrouter/qwen/qwen3.6-plus:free |

## Quick Start

```bash
# Install
pip install -e .

# Configure API keys
cp .env.example .env
# Edit .env — add OPENROUTER_API_KEY and GROQ_API_KEY

# Start
python -m freerouter
```

Server runs on `http://0.0.0.0:4000`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | Chat completions (OpenAI-compatible) |
| GET | `/v1/models` | List available task routes |
| GET | `/health` | Health check |

## Usage

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:4000/v1", api_key="any_key")

response = client.chat.completions.create(
    model="script_writer",
    messages=[{"role": "user", "content": "Write a YouTube intro about quantum physics"}],
)
print(response.choices[0].message.content)
```

### cURL

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer any_key" \
  -d '{
    "model": "scorer",
    "messages": [{"role": "user", "content": "Rate this script: Hello world"}]
  }'
```

### Health Check

```bash
curl http://localhost:4000/health
```

Response:
```json
{
  "status": "ok",
  "version": "3.0.0",
  "tasks": ["auto", "researcher", "topic_finder", "script_writer", "scorer", "challenger", "annotator"]
}
```

## Configuration

Set API keys in `freerouter/.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-...   # required — all routes use OpenRouter free models
GROQ_API_KEY=gsk_...               # optional — currently not in routing table
OLLAMA_BASE_URL=http://localhost:11434   # optional — for local Ollama models
```

Currently only **OpenRouter** free models are in the routing table. Groq key is kept for future use.

## Architecture

```
freerouter/
├── __init__.py      # Package init, exports ROUTES and __version__
├── __main__.py      # Entry point: python -m freerouter
├── config.py        # ROUTES table (task → model mapping)
├── server.py        # FastAPI app with /v1/chat/completions, /v1/models, /health
└── storage.py       # SQLite pipeline task storage
```

~200 lines total. Provider management, fallbacks, and rate limiting are all handled by LiteLLM.

## Stopping the Server

Press `Ctrl+C` in the terminal where freerouter is running.

## Troubleshooting

### Port already in use
```bash
lsof -i :4000 && kill -9 <PID>
```

### Check if running
```bash
curl http://localhost:4000/health
```

### Model fails / both primary and fallback down
The server returns HTTP 503 and your app's RouterClient will automatically retry with `"auto"`.

## License

MIT
