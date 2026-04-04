# FreeRouter

> **LiteLLM-based task router — always free**

FreeRouter v3 is a slim OpenAI-compatible proxy built on [LiteLLM](https://github.com/BerriAI/litellm). Send a task name as the `model` field and FreeRouter resolves it to the best free model with automatic fallback.

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────────────┐
│  Your App    │────▶│   FreeRouter    │────▶│  openrouter/.../model:free│
│  (OpenAI SDK)│     │  localhost:4000 │     │  groq/...                │
└──────────────┘     └─────────────────┘     └──────────────────────────┘
```

## Named Routes

| Route | Primary Model | Fallback |
|-------|--------------|----------|
| `auto` | openrouter/stepfun/step-3.5-flash:free | groq/llama-3.3-70b-versatile |
| `researcher` | openrouter/stepfun/step-3.5-flash:free | openrouter/qwen/qwen3.6-plus:free |
| `topic_finder` | openrouter/qwen/qwen3.6-plus:free | openrouter/stepfun/step-3.5-flash:free |
| `script_writer` | openrouter/qwen/qwen3.6-plus:free | openrouter/mistralai/mistral-small-3.1:free |
| `scorer` | groq/compound-beta-mini | groq/llama-3.1-8b-instant |
| `challenger` | groq/llama-3.1-8b-instant | groq/llama-3.3-70b-versatile |
| `annotator` | groq/qwen-qwq-32b | groq/llama-3.1-8b-instant |

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
OPENROUTER_API_KEY=sk-or-v1-...   # required
GROQ_API_KEY=gsk_...               # required
OLLAMA_BASE_URL=http://localhost:11434   # optional
```

Only two providers are used: **OpenRouter** and **Groq**.

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

## Docker

```bash
docker build -t freerouter .
docker run -p 4000:4000 --env-file .env freerouter
```

## License

MIT
