# Step-by-Step Guide: Pull and Run AI-Orchestration

This guide will walk you through pulling the code from GitHub and running the AI-Orchestration system.

---

## 📋 Prerequisites

Before starting, make sure you have:

| Requirement | Version | How to Check | How to Install |
|-------------|---------|--------------|----------------|
| Python | **3.10+** | `python --version` | Download from python.org |
| pip | Latest | `pip --version` | `python -m pip install --upgrade pip` |
| Git | Any | `git --version` | Download from git-scm.com |
| (Optional) Redis | Any | `redis-cli ping` | For production rate limiting |

> ✅ Python 3.10, 3.11, 3.12, 3.13, and 3.14 are all supported.

### API Keys You'll Need

| Key | Where to Get It | Required For |
|-----|-----------------|--------------|
| `GROQ_API_KEY` | console.groq.com | LLM Chat (Required) |
| `OPENROUTER_API_KEY` | openrouter.ai | Alternative LLMs (Optional) |
| `ZEP_API_KEY` | app.getzep.com | Agent Memory (Optional) |
| `YOUTUBE_API_KEY` | Google Cloud Console | YouTube Analytics (Optional) |
| `NOTION_API_KEY` | notion.so/my-integrations | Notion Integration (Optional) |

---

## Step 1: Clone the Repository

Open your terminal (Command Prompt on Windows, Terminal on Mac/Linux) and run:

```bash
# Navigate to your projects folder
cd ~/projects

# Clone the repository
git clone https://github.com/HassanArif-collab/AI-Orchestration.git

# Enter the project directory
cd AI-Orchestration
```

**Expected Output:**
```
Cloning into 'AI-Orchestration'...
remote: Enumerating objects: 500+, done.
remote: Counting objects: 100% (500/500), done.
remote: Compressing objects: 100% (300/300), done.
remote: Total 500+ (delta 200), reused 400+ (delta 150), pack-reused 0
Receiving objects: 100% (500/500), 2.00 MiB | 5.00 MiB/s, done.
Resolving deltas: 100% (200/200), done.
```

---

## Step 2: Create Virtual Environment (Recommended)

This keeps dependencies isolated from your system Python.

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate
```

**Expected Output:**
```
# Your prompt should now show (venv) at the beginning:
(venv) user@computer:~/projects/AI-Orchestration$
```

---

## Step 3: Install Dependencies

```bash
# Install all dependencies (including optional features)
pip install -e ".[all]"

# Or install minimal dependencies only
pip install -e .
```

**Expected Output:**
```
Successfully installed ai-orchestration-0.1.0 httpx-0.27.0 openai-1.0.0 pydantic-2.0.0 ...
```

---

## Step 4: Configure Environment Variables

### 4.1 Main Application Environment

```bash
# Copy the example file
cp .env.example .env

# Edit the .env file
# On Windows:
notepad .env

# On Mac:
open -a TextEdit .env

# On Linux:
nano .env
```

**Add at minimum:**
```env
# FreeRouter Proxy URL (default is fine for local)
FREEROUTER_URL=http://localhost:4000

# Logging level
LOG_LEVEL=INFO

# Feature flags
ASSET_CREATION_ENABLED=true
PUBLISH_ENABLED=true
```

### 4.2 FreeRouter Environment (for LLM access)

```bash
# Navigate to freerouter folder
cd freerouter

# Copy the example file
cp .env.example .env

# Edit the .env file and add your Groq API key
nano .env
```

**Required in `freerouter/.env`:**
```env
# At minimum, add your Groq API key (free from console.groq.com)
GROQ_API_KEY=your_groq_api_key_here

# Optional: OpenRouter for more model choices
OPENROUTER_API_KEY=your_openrouter_key_here
```

**Go back to project root:**
```bash
cd ..
```

---

## Step 5: Run the System

You need **TWO terminal windows** open.

### Terminal 1: FreeRouter Proxy (LLM Gateway)

```bash
# Navigate to project
cd ~/projects/AI-Orchestration

# Activate virtual environment
source venv/bin/activate  # Mac/Linux
# OR: venv\Scripts\activate  # Windows

# Run FreeRouter proxy on port 4000
python -m freerouter proxy
```

**Expected Output:**
```
2026-03-26 10:00:00 INFO     Loading providers from environment...
2026-03-26 10:00:00 INFO     Groq provider configured
2026-03-26 10:00:00 INFO     Starting FreeRouter proxy server...
2026-03-26 10:00:00 INFO     Uvicorn running on http://0.0.0.0:4000
```

### Terminal 2: Web Dashboard

```bash
# Navigate to project
cd ~/projects/AI-Orchestration

# Activate virtual environment
source venv/bin/activate  # Mac/Linux
# OR: venv\Scripts\activate  # Windows

# Run the web dashboard on port 3000
python -m apps.api.main
```

**Expected Output:**
```
2026-03-26 10:01:00 INFO     Starting AI-Orchestration Dashboard...
2026-03-26 10:01:00 INFO     Loaded configuration from .env
2026-03-26 10:01:00 INFO     Uvicorn running on http://0.0.0.0:3000
2026-03-26 10:01:00 INFO     Dashboard ready at http://localhost:3000
```

---

## Step 6: Access the Dashboard

Open your web browser and go to:

```
http://localhost:3000
```

**You should see:**
- A dark-themed dashboard
- Navigation tabs: Pipeline, Chat, Providers, Memory, Analytics, Visual, Settings
- Real-time connection status (green indicator)

---

## What You'll See in Each Tab

### 📊 Pipeline Tab
- Create new video production runs
- View pipeline stages and their status
- Approve or reject human gates
- See stage outputs and progress

### 💬 Chat Tab
- Direct chat with LLM providers
- Select different models (Groq, OpenRouter)
- View conversation history

### 🔧 Providers Tab
- See LLM provider status (Healthy/Unhealthy)
- Configure API keys
- View rate limits and circuit breaker status

### 🧠 Memory Tab
- Browse Zep Cloud memory sessions
- View stored facts about users
- Search through conversation history

### 📈 Analytics Tab
- YouTube channel statistics
- Competitor tracking
- Performance metrics

### 🎨 Visual Tab
- Video asset management
- Remotion render status
- Visual manifest browser

### ⚙️ Settings Tab
- System health status
- Configuration overview
- Feature flags

---

## API Endpoints (for Developers)

### Check System Health
```bash
curl http://localhost:3000/api/health
```

**Expected Output:**
```json
{
  "status": "healthy",
  "freerouter": "connected",
  "providers": ["groq"],
  "version": "0.1.0"
}
```

### Create a Pipeline Run
```bash
curl -X POST http://localhost:3000/api/pipeline/runs
```

**Expected Output:**
```json
{
  "id": "run_abc123",
  "status": "pending",
  "created_at": "2026-03-26T10:00:00Z",
  "stages": [...]
}
```

### Chat with LLM
```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?", "provider": "groq"}'
```

---

## Troubleshooting

### Problem: "Module not found" error
**Solution:**
```bash
pip install -e ".[all]"
```

### Problem: "Connection refused" to FreeRouter
**Solution:** Make sure Terminal 1 is running FreeRouter:
```bash
python -m freerouter proxy
```

### Problem: "GROQ_API_KEY not set"
**Solution:** Edit `freerouter/.env` and add your Groq API key:
```bash
GROQ_API_KEY=gsk_your_key_here
```

### Problem: Port 3000 or 4000 already in use
**Solution:** Kill the process using that port or change the port:
```bash
# Find what's using port 3000
lsof -i :3000  # Mac/Linux
netstat -ano | findstr :3000  # Windows

# Or run on different port
PORT=3001 python -m apps.api.main
```

### Problem: Circuit breaker shows "OPEN"
**Solution:** The provider has failed multiple times. Wait 60 seconds for recovery or restart FreeRouter.

---

## Quick Reference Commands

| Action | Command |
|--------|---------|
| Clone repo | `git clone https://github.com/HassanArif-collab/AI-Orchestration.git` |
| Pull latest | `git pull origin main` |
| Install deps | `pip install -e ".[all]"` |
| Run FreeRouter | `python -m freerouter proxy` |
| Run Dashboard | `python -m apps.api.main` |
| Run tests | `pytest tests/` |
| Check health | `curl http://localhost:3000/api/health` |

---

## What Happens When You Run the Pipeline

1. **Topic Selection** - Finds trending topics
2. **Research** - Gathers information from web
3. **Script Writing** - Creates video script
4. **Visual Planning** - Plans visual elements
5. **Asset Creation** - Generates video assets
6. **Review Gate** - Human approval checkpoint
7. **Refinement** - Improves based on feedback
8. **Final Render** - Produces final video
9. **Publishing** - Prepares for upload

Each stage saves output to memory and triggers escalation alerts if quality scores are too low.

---

## Next Steps

1. **Get a Groq API key** (free) from console.groq.com
2. **Start FreeRouter** in Terminal 1
3. **Start Dashboard** in Terminal 2
4. **Open http://localhost:3000** in your browser
5. **Try the Chat tab** to verify LLM connection
6. **Create a pipeline run** from the Pipeline tab

Happy coding! 🚀
