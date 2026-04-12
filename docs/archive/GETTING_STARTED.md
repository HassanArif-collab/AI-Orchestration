# Getting Started

Step-by-step guide to pull, setup, and run AI-Orchestration.

## Why This Setup?

This system has specific requirements that might differ from typical Python projects:

| Requirement | Reason |
|-------------|--------|
| Two terminals | FreeRouter (LLM proxy) and main API run as separate services |
| Two .env files | LLM keys are isolated in FreeRouter for security |
| No database setup | SQLite is zero-config and file-based |
| API key required | The system needs an LLM for content generation |

---

## Prerequisites

| Requirement | Version | How to Check |
|-------------|---------|--------------|
| Python | **3.10+** | `python --version` |
| pip | Latest | `pip --version` |
| Git | Any | `git --version` |

✅ Python 3.10, 3.11, 3.12, 3.13, and 3.14 are all supported.

### API Keys

| Key | Where to Get | Required |
|-----|--------------|----------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) | **Yes** |
| `OPENROUTER_API_KEY` | [openrouter.ai](https://openrouter.ai) | Optional (alternative) |
| `ZEP_API_KEY` | [app.getzep.com](https://app.getzep.com) | Optional (memory) |
| `YOUTUBE_API_KEY` | Google Cloud Console | Optional (analytics) |

---

## Quick Setup (5 minutes)

### 1. Clone and Install

```bash
git clone https://github.com/HassanArif-collab/AI-Orchestration.git
cd AI-Orchestration
pip install -e ".[all]"
```

### 2. Configure FreeRouter

```bash
cd freerouter
cp .env.example .env
# Edit .env and add: GROQ_API_KEY=your_key_here
cd ..
```

### 3. Configure Main App

```bash
cp .env.example .env
# Optional: Add ZEP_API_KEY, YOUTUBE_API_KEY
```

### 4. Start Services (Two Terminals)

**Terminal 1 - FreeRouter:**
```bash
python -m freerouter proxy
```

**Terminal 2 - Dashboard:**
```bash
python -m apps.api.main
```

Open **http://localhost:3000**

---

## Detailed Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/HassanArif-collab/AI-Orchestration.git
cd AI-Orchestration
```

### Step 2: Virtual Environment (Recommended)

```bash
python -m venv venv

# Activate
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
```

### Step 3: Install Dependencies

```bash
pip install -e ".[all]"
```

### Step 4: Configure Environment

**Main app (`.env`):**
```env
FREEROUTER_URL=http://localhost:4000
LOG_LEVEL=INFO
```

**FreeRouter (`freerouter/.env`):**
```env
GROQ_API_KEY=your_groq_key_here
OPENROUTER_API_KEY=your_openrouter_key_here  # Optional
```

### Step 5: Run the System

You need **two terminal windows**.

**Terminal 1 - FreeRouter (port 4000):**
```bash
python -m freerouter proxy
```

Expected output:
```
INFO Loading providers from environment...
INFO Groq provider configured
INFO Uvicorn running on http://0.0.0.0:4000
```

**Terminal 2 - Dashboard (port 3000):**
```bash
python -m apps.api.main
```

Expected output:
```
INFO Starting AI-Orchestration Dashboard...
INFO Uvicorn running on http://0.0.0.0:3000
```

---

## Dashboard Tabs

| Tab | Purpose |
|-----|---------|
| Pipeline | Create runs, approve gates, view outputs |
| Chat | Direct LLM conversation |
| Providers | Monitor LLM health |
| Memory | Browse agent memory |
| Analytics | YouTube stats |
| Settings | System health |

---

## Troubleshooting

### "Connection refused" to FreeRouter

**Why this happens**: FreeRouter must start before the main API.

**Solution**: Start FreeRouter first in Terminal 1, wait for "Uvicorn running" message, then start the dashboard.

### "GROQ_API_KEY not set"

**Why this happens**: LLM keys live in `freerouter/.env`, not the root `.env`.

**Solution**: Edit `freerouter/.env` and add your Groq API key.

### "Port 3000 already in use"

**Solution**: Kill the process or use a different port:
```bash
PORT=3001 python -m apps.api.main
```

### "Module not found"

**Solution**: Install all dependencies:
```bash
pip install -e ".[all]"
```

### Circuit breaker shows "OPEN"

**Why this happens**: Provider has failed multiple times.

**Solution**: Wait 60 seconds for recovery or restart FreeRouter.

---

## API Quick Reference

```bash
# Check health
curl http://localhost:3000/api/health

# Create pipeline run
curl -X POST http://localhost:3000/api/pipeline/runs

# Chat with LLM
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

---

## What Happens When You Run a Pipeline

1. **Topic Selection** - Discovers trending topics
2. **Human Gate** - You pick a topic
3. **Research** - Gathers information
4. **Script Writing** - Creates video script
5. **Human Gate** - You review the script
6. **Asset Creation** - Generates assets
7. **Publishing** - Prepares output

---

## Next Steps

1. Get a free Groq API key from [console.groq.com](https://console.groq.com)
2. Start FreeRouter in Terminal 1
3. Start Dashboard in Terminal 2
4. Open http://localhost:3000
5. Try the Chat tab to verify LLM connection
6. Create a pipeline run from the Pipeline tab
