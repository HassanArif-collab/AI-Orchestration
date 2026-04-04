# FreeRouter Usage Guide

> **How to use FreeRouter v3 — a slim LiteLLM task router**

## Quick Start

```bash
# 1. Install
pip install -e .

# 2. Configure
cp .env.example .env
# Edit .env and add your API keys:
#   OPENROUTER_API_KEY=sk-or-v1-...
#   GROQ_API_KEY=gsk_...

# 3. Start
python -m freerouter
```

Server runs at `http://localhost:4000`.

## Configuration

### Environment Variables

Create/edit `freerouter/.env`:

```bash
# Required — get free keys at:
#   OpenRouter: https://openrouter.ai/keys
#   Groq:       https://console.groq.com/keys
OPENROUTER_API_KEY=sk-or-v1-your-key-here
GROQ_API_KEY=gsk_your-key-here

# Optional — for local models via Ollama
OLLAMA_BASE_URL=http://localhost:11434
```

Only two providers are needed: **OpenRouter** and **Groq**.

### Named Routes

Use any of these as the `model` parameter:

| Route | Use Case | Primary Model | Provider |
|-------|----------|--------------|----------|
| `auto` | General purpose fallback | step-3.5-flash:free | OpenRouter |
| `researcher` | Deep research, synthesis | step-3.5-flash:free | OpenRouter |
| `topic_finder` | Creative ideation, gap analysis | qwen3.6-plus:free | OpenRouter |
| `script_writer` | Script writing, creative prose | qwen3.6-plus:free | OpenRouter |
| `scorer` | Fast pass/fail scoring | compound-beta-mini | Groq |
| `challenger` | JSON rewrite, structured output | llama-3.1-8b-instant | Groq |
| `annotator` | Visual cue generation | qwen-qwq-32b | Groq |

You can also pass a direct LiteLLM model string (e.g., `groq/llama-3.3-70b-versatile`) — it will pass through with `auto` fallback.

## Using with Applications

### OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:4000/v1", api_key="any_key")

# Research a topic
response = client.chat.completions.create(
    model="researcher",
    messages=[{"role": "user", "content": "Research the history of quantum computing"}],
)
print(response.choices[0].message.content)

# Generate a script
response = client.chat.completions.create(
    model="script_writer",
    messages=[{"role": "user", "content": "Write a YouTube script about black holes"}],
)
print(response.choices[0].message.content)

# Score content quality
response = client.chat.completions.create(
    model="scorer",
    messages=[{"role": "user", "content": "Rate this script on a scale of 1-10: Hello world..."}],
)
print(response.choices[0].message.content)

# Generate topic ideas
response = client.chat.completions.create(
    model="topic_finder",
    messages=[{"role": "user", "content": "Suggest 5 trending YouTube topics about AI in 2025"}],
)
print(response.choices[0].message.content)

# General purpose (auto)
response = client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Explain quantum entanglement"}],
)
print(response.choices[0].message.content)
```

### Streaming

```python
stream = client.chat.completions.create(
    model="script_writer",
    messages=[{"role": "user", "content": "Write a short poem"}],
    stream=True,
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

### cURL

```bash
# Script writing
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer any_key" \
  -d '{
    "model": "script_writer",
    "messages": [{"role": "user", "content": "Write an intro about space exploration"}]
  }'

# Scoring
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer any_key" \
  -d '{
    "model": "scorer",
    "messages": [{"role": "user", "content": "Score: The quick brown fox jumps over the lazy dog"}]
  }'

# List models
curl http://localhost:4000/v1/models

# Health check
curl http://localhost:4000/health
```

### LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="topic_finder",
    base_url="http://localhost:4000/v1",
    api_key="any_key",
)

response = llm.invoke("Suggest YouTube topics about machine learning")
print(response.content)
```

### JavaScript / Node.js

```javascript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'http://localhost:4000/v1',
  apiKey: 'any_key',
});

const response = await client.chat.completions.create({
  model: 'script_writer',
  messages: [{ role: 'user', content: 'Write a video intro about AI' }],
});

console.log(response.choices[0].message.content);
```

## Endpoints

### POST /v1/chat/completions

Standard OpenAI-compatible chat completions. Set `model` to a task name.

```python
client.chat.completions.create(
    model="annotator",          # task name or direct litellm string
    messages=[...],
    temperature=0.7,
    max_tokens=1000,
    stream=False,               # or True for streaming
)
```

Response includes headers:
- `x-freerouter-model` — actual model used
- `x-freerouter-provider` — provider (groq / openrouter)

### GET /v1/models

Returns all available task routes:

```json
{
  "object": "list",
  "data": [
    {
      "id": "auto",
      "object": "model",
      "owned_by": "openrouter",
      "primary": "openrouter/stepfun/step-3.5-flash:free",
      "fallback": "groq/llama-3.3-70b-versatile"
    }
  ]
}
```

### GET /health

```json
{
  "status": "ok",
  "version": "3.0.0",
  "tasks": ["auto", "researcher", "topic_finder", "script_writer", "scorer", "challenger", "annotator"]
}
```

## Troubleshooting

### API key errors

```bash
# Verify keys in .env
cat .env | grep API_KEY

# Test OpenRouter key
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

### Connection refused

```bash
# Check if FreeRouter is running
curl http://localhost:4000/health
```

### All models failed (503)

FreeRouter returns HTTP 503 when both the primary and fallback model fail. Check:
1. API keys are valid
2. Provider is not rate-limited
3. Models exist on the provider

### Port already in use

FreeRouter v3 hardcodes port 4000. Change `__main__.py` if you need a different port.
