# FreeRouter Usage Guide

> **Complete guide to using FreeRouter for free LLM access**

This guide shows you how to set up and use FreeRouter to access powerful LLMs for free.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Starting the Server](#starting-the-server)
5. [Web Dashboard](#web-dashboard) 🆕
6. [Using with Applications](#using-with-applications)
7. [Model Selection Guide](#model-selection-guide)
8. [Auto-Routing](#auto-routing)
9. [Web Search Feature](#web-search-feature)
10. [API Reference](#api-reference)
11. [Troubleshooting](#troubleshooting)

---

## Quick Start

Get up and running in 5 minutes:

```bash
# 1. Clone and enter directory
git clone https://github.com/freerouter/freerouter.git
cd freerouter

# 2. Create virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Install dependencies
pip install -e .

# 4. Set up environment
cp .env.example .env
# Edit .env and add your API keys

# 5. Start Ollama (for local models)
ollama serve &
ollama pull qwen2.5:7b

# 6. Start FreeRouter
freerouter start
```

Your proxy is now running at `http://localhost:4000`

---

## Installation

### Option 1: pip (Recommended for Development)

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install package in editable mode
pip install -e .
```

### Option 2: Docker

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f freerouter
```

### Prerequisites

1. **Python 3.10+** (for pip installation)
2. **Ollama** (optional, for local models)
   ```bash
   # Install from https://ollama.ai
   # Then pull recommended models:
   ollama pull qwen2.5:7b
   ollama pull qwen2.5-coder:32b
   ollama pull llama3.2-vision:11b
   ```

3. **API Keys** (get free tiers):
   - [OpenRouter](https://openrouter.ai/keys) - Free tier available
   - [Groq](https://console.groq.com/keys) - Free tier available

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# ============================================
# REQUIRED - Get free tiers at:
# OpenRouter: https://openrouter.ai/keys
# Groq: https://console.groq.com/keys
# ============================================
OPENROUTER_API_KEY=sk-or-v1-your-key-here
GROQ_API_KEY=gsk_your-key-here

# ============================================
# OPTIONAL - Paid providers
# ============================================
# ANTHROPIC_API_KEY=your-key
# OPENAI_API_KEY=your-key

# ============================================
# FREEROUTER SETTINGS
# ============================================
# Custom config file (optional)
# FREEROUTER_CONFIG=/path/to/config.yaml

# Proxy API key (optional, for authentication)
# FREEROUTER_API_KEY=your-proxy-key
```

### Model Aliases Available

| Alias | Primary Model | Fallback Chain |
|-------|--------------|----------------|
| `free-router/fast` | Ollama Qwen 2.5 7B | Groq Llama 3.3 70B → OpenRouter Llama 3.3 70B |
| `free-router/coder` | Ollama Qwen 2.5 Coder 32B | OpenRouter DeepSeek → OpenRouter Qwen Coder → Groq |
| `free-router/reasoning` | OpenRouter DeepSeek R1 | Ollama DeepSeek R1 8B |
| `free-router/smart` | Ollama Qwen 2.5 14B | Groq Qwen 2.5 32B → OpenRouter Qwen 2.5 32B |
| `free-router/vision` | Ollama Llama 3.2 Vision 11B | OpenRouter Llama Vision → Ollama Qwen VL |
| `free-router/long-context` | Ollama Qwen 2.5 32B | OpenRouter Llama 3.3 70B (128k) |
| `free-router/balanced` | Ollama Qwen 2.5 7B | Groq → OpenRouter |
| `free-router/auto` | **Auto-selected based on task** | Dynamic |

---

## Starting the Server

### Basic Start

```bash
# Start with default settings
freerouter start

# Server runs at http://localhost:4000
```

### Custom Options

```bash
# Custom host and port
freerouter start --host 0.0.0.0 --port 8080

# Custom config file
freerouter start --config /path/to/config.yaml

# Multiple workers
freerouter start --workers 4

# Debug mode
freerouter start --debug
```

### Check Status

```bash
# View available models
freerouter config

# Check environment
freerouter env

# Check version
freerouter version
```

### Verify It's Running

```bash
# Health check
curl http://localhost:4000/health

# Expected response:
# {"status": "healthy", "version": "1.0.0", "providers": {...}}
```

---

## Web Dashboard

FreeRouter includes a browser-based dashboard for easy management. This is the **easiest way** to configure and use FreeRouter.

### Start the Dashboard

```bash
# Start the web dashboard (opens browser automatically)
freerouter web

# Custom port
freerouter web --port 3000

# Don't open browser automatically
freerouter web --no-open

# Specify proxy port if different from 4000
freerouter web --proxy-port 4001
```

The dashboard runs at `http://127.0.0.1:8080` by default.

### Dashboard Features

#### 1. **Providers Tab** - Manage API Keys

- View all supported providers (Ollama, Groq, OpenRouter, etc.)
- See which providers are configured and working
- Add/update API keys directly from the browser
- Test provider connections
- View rate limit status

![Providers Tab](docs/providers-tab.png)

#### 2. **Chat Test Tab** - Test Models

- Select from available models (`free-router/auto`, `free-router/coder`, etc.)
- Send test messages to verify everything works
- See which model was selected for auto-routing

#### 3. **Configuration Tab** - Export Settings

Copy-paste ready configurations for:
- **Cursor IDE**: Settings to connect Cursor
- **VS Code + Continue**: JSON config for Continue extension
- **Python**: Code snippet using OpenAI SDK
- **cURL**: Command-line test

#### 4. **Usage Tab** - Monitor Rate Limits

- View rate limit status for each provider
- See requests remaining/used
- Identify providers near limits

### Security

The dashboard is **localhost-only** by default (`127.0.0.1`), ensuring:
- Only you can access it
- API keys stay on your machine
- No external network exposure

For production use, you can add authentication:
```bash
# Set an authentication password
export FREEROUTER_WEB_KEY=your-secret-password
freerouter web --host 0.0.0.0
```

---

## Using with Applications

### Claude Code

Set environment variables before running Claude Code:

```bash
# In your shell or ~/.bashrc / ~/.zshrc
export ANTHROPIC_BASE_URL=http://localhost:4000
export ANTHROPIC_API_KEY=any_value

# Now run Claude Code
claude-code
```

### Cursor IDE

1. Open Settings (`Ctrl/Cmd + ,`)
2. Navigate to **Models**
3. Configure:
   - **OpenAI API Base URL**: `http://localhost:4000/v1`
   - **OpenAI API Key**: `any_value` (or your FreeRouter API key)
4. Select model: `free-router/smart` or any other alias

### Continue (VS Code Extension)

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
    },
    {
      "title": "FreeRouter Coder",
      "provider": "openai",
      "model": "free-router/coder",
      "apiBase": "http://localhost:4000/v1",
      "apiKey": "any_key"
    },
    {
      "title": "FreeRouter Auto",
      "provider": "openai",
      "model": "free-router/auto",
      "apiBase": "http://localhost:4000/v1",
      "apiKey": "any_key"
    }
  ]
}
```

### OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:4000/v1",
    api_key="any_key"  # FreeRouter doesn't require auth by default
)

# Simple chat
response = client.chat.completions.create(
    model="free-router/smart",
    messages=[
        {"role": "user", "content": "Explain quantum computing in one paragraph"}
    ]
)
print(response.choices[0].message.content)

# Code generation
response = client.chat.completions.create(
    model="free-router/coder",
    messages=[
        {"role": "user", "content": "Write a Python function to merge sort a list"}
    ]
)
print(response.choices[0].message.content)

# Auto-routing (classifies task automatically)
response = client.chat.completions.create(
    model="free-router/auto",
    messages=[
        {"role": "user", "content": "Debug this code: def foo(x): return x/0"}
    ]
)
# Routes to free-router/coder automatically
```

### LangChain

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="free-router/smart",
    base_url="http://localhost:4000/v1",
    api_key="any_key"
)

response = llm.invoke("What is the meaning of life?")
print(response.content)
```

### JavaScript / Node.js

```javascript
import OpenAI from 'openai';

const client = new OpenAI({
  baseURL: 'http://localhost:4000/v1',
  apiKey: 'any_key'
});

async function chat(message) {
  const response = await client.chat.completions.create({
    model: 'free-router/smart',
    messages: [{ role: 'user', content: message }]
  });
  return response.choices[0].message.content;
}

// Usage
const answer = await chat('Hello, how are you?');
console.log(answer);
```

### cURL

```bash
# Basic request
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer any_key" \
  -d '{
    "model": "free-router/smart",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# With streaming
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer any_key" \
  -d '{
    "model": "free-router/fast",
    "messages": [{"role": "user", "content": "Tell me a joke"}],
    "stream": true
  }'
```

---

## Model Selection Guide

### When to Use Each Model

| Use Case | Recommended Model | Why |
|----------|------------------|-----|
| Simple chat, quick Q&A | `free-router/fast` | Fast, local, no rate limits |
| Code generation | `free-router/coder` | Qwen Coder 32B optimized for code |
| Debugging | `free-router/coder` | DeepSeek excels at understanding code |
| Complex reasoning | `free-router/reasoning` | DeepSeek R1 for chain-of-thought |
| Math problems | `free-router/reasoning` | Best for logical reasoning |
| Image analysis | `free-router/vision` | Supports image input |
| Long documents | `free-router/long-context` | 32k+ context window |
| Multi-step tasks | `free-router/smart` | Good balance of speed and intelligence |
| Unknown task type | `free-router/auto` | Automatically classifies and routes |

### Performance Comparison

| Model | Speed | Intelligence | Cost |
|-------|-------|--------------|------|
| `fast` | ★★★★★ | ★★★☆☆ | FREE |
| `coder` | ★★★☆☆ | ★★★★★ | FREE |
| `reasoning` | ★★☆☆☆ | ★★★★★ | FREE |
| `smart` | ★★★☆☆ | ★★★★☆ | FREE |
| `vision` | ★★★☆☆ | ★★★☆☆ | FREE |
| `long-context` | ★★☆☆☆ | ★★★★☆ | FREE |

---

## Auto-Routing

Use `free-router/auto` to let FreeRouter automatically select the best model:

```python
response = client.chat.completions.create(
    model="free-router/auto",
    messages=[{"role": "user", "content": "..."}]
)
```

### How It Works

1. **Content Analysis**: FreeRouter analyzes your message content
2. **Keyword Detection**: Uses pattern matching to identify task type
3. **Category Assignment**: Classifies into one of:
   - `simple_chat` → Routes to `free-router/fast`
   - `coding` → Routes to `free-router/coder`
   - `reasoning` → Routes to `free-router/reasoning`
   - `vision` → Routes to `free-router/vision`
   - `agentic` → Routes to `free-router/smart`
   - `research` → Routes to `free-router/long-context`

### Examples

```python
# Automatically routes to free-router/coder
response = client.chat.completions.create(
    model="free-router/auto",
    messages=[{"role": "user", "content": "Write a Python function to sort a list"}]
)

# Automatically routes to free-router/reasoning
response = client.chat.completions.create(
    model="free-router/auto",
    messages=[{"role": "user", "content": "If 2x + 5 = 15, what is x?"}]
)

# Automatically routes to free-router/vision (with image)
response = client.chat.completions.create(
    model="free-router/auto",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
        ]
    }]
)
```

---

## Web Search Feature

FreeRouter can intercept web search tool calls and execute them automatically:

### How It Works

When a request includes a tool call for web search, FreeRouter:
1. Detects the search intent
2. Executes the search via DuckDuckGo (no API key needed)
3. Injects results into the conversation
4. Returns the enhanced response

### Using with Tool Calls

```python
response = client.chat.completions.create(
    model="free-router/smart",
    messages=[{"role": "user", "content": "What are the latest AI news?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                }
            }
        }
    }]
)
# FreeRouter intercepts and executes the search automatically
```

### Automatic Search Detection

Even without explicit tool calls, FreeRouter detects search intent:

```python
# These phrases trigger automatic web search:
# - "What is the latest news about..."
# - "Search for..."
# - "What happened recently..."
# - "Current status of..."

response = client.chat.completions.create(
    model="free-router/smart",
    messages=[{"role": "user", "content": "What's the latest news about GPT-5?"}]
)
# Automatically injects search results into context
```

---

## API Reference

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completions (OpenAI compatible) |
| `/v1/models` | GET | List available models |
| `/health` | GET | Health check with provider status |
| `/status` | GET | Detailed status information |
| `/docs` | GET | API documentation (Swagger) |

### Chat Completion Request

```python
response = client.chat.completions.create(
    model="free-router/smart",  # Required
    messages=[                  # Required
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"}
    ],
    temperature=0.7,           # Optional: 0-2, default 1
    max_tokens=1000,           # Optional: max output tokens
    stream=False,              # Optional: enable streaming
    tools=[...],               # Optional: tool definitions
)
```

### Streaming Response

```python
stream = client.chat.completions.create(
    model="free-router/fast",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### Vision Request

```python
response = client.chat.completions.create(
    model="free-router/vision",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "https://example.com/image.jpg"
                    # Or base64: "url": "data:image/jpeg;base64,..."
                }
            }
        ]
    }]
)
```

---

## Troubleshooting

### Ollama Not Running

**Symptom**: `Connection refused` for local models

**Solution**:
```bash
# Start Ollama
ollama serve

# Pull required models
ollama pull qwen2.5:7b
ollama pull qwen2.5-coder:32b
```

### API Key Errors

**Symptom**: `401 Unauthorized` from providers

**Solution**:
```bash
# Check your environment
freerouter env

# Verify keys in .env
cat .env | grep API_KEY

# Test keys manually
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

### Model Not Found

**Symptom**: `Model not found` error

**Solution**:
```bash
# List available models
freerouter config

# Use correct alias
# Valid: free-router/smart, free-router/coder, etc.
# Invalid: gpt-4, claude-3, etc.
```

### Rate Limiting

**Symptom**: `429 Too Many Requests`

**Solution**:
- FreeRouter automatically falls back to alternative models
- Check rate limits: Groq (30 req/min), OpenRouter (varies)
- Use local Ollama models (no rate limits)

### Port Already in Use

**Symptom**: `Address already in use`

**Solution**:
```bash
# Use different port
freerouter start --port 4001

# Or kill existing process
# Linux/Mac:
lsof -i :4000 && kill -9 <PID>
# Windows:
netstat -ano | findstr :4000
taskkill /PID <PID> /F
```

### Slow Responses

**Symptom**: Long wait times

**Solution**:
```bash
# Use faster models for simple tasks
# free-router/fast uses local Ollama (fastest)

# Check provider health
curl http://localhost:4000/health

# If Ollama is slow, use Groq (very fast inference)
# Switch to free-router/fast-groq
```

### Fallback Not Working

**Symptom**: Errors instead of fallback

**Solution**:
- Check LiteLLM logs for fallback details
- Verify fallback configuration in `config/proxy_server_config.yaml`
- Ensure multiple providers have valid API keys

---

## Advanced Usage

### Custom Configuration

Create your own config file:

```yaml
# custom_config.yaml
model_list:
  - model_name: my-custom-model
    litellm_params:
      model: "ollama/my-model:latest"
      api_base: "http://localhost:11434"

fallbacks:
  - model: "my-custom-model"
    fallbacks: ["free-router/smart"]
```

```bash
freerouter start --config custom_config.yaml
```

### Multiple Proxies

Run multiple FreeRouter instances:

```bash
# Terminal 1: Main proxy
freerouter start --port 4000

# Terminal 2: Dedicated coder proxy
freerouter start --port 4001 --config coder_config.yaml
```

### Programmatic Usage

```python
from freerouter import TaskClassifier, WebSearchInterceptor

# Use classifier directly
classifier = TaskClassifier(use_fast_classifier=False)
result = classifier.classify("Write a Python function")
print(result.category)  # TaskCategory.CODING
print(result.recommended_model)  # free-router/coder

# Use web search directly
searcher = WebSearchInterceptor()
response = searcher.execute_search("Python tutorials")
for result in response.results:
    print(f"{result.title}: {result.url}")
```

---

## Getting Help

- **Documentation**: Check this guide and `README.md`
- **Issues**: Open an issue on GitHub
- **Logs**: Run with `--debug` for verbose output

---

**Happy free LLM usage!**