# Implementation Plan V3: Self-Evolving Script Generation System

**Branch:** `Explaining-FinalRefactoring`
**Date:** 2025-03-25
**Status:** PLANNING PHASE - NOT IMPLEMENTING YET

---

## Corrections Applied

| Item | Previous | Corrected |
|------|----------|-----------|
| Provider Name | Grok (X.AI) | **Groq** already exists; **Grok** is X.AI's model |
| Trend Sources | 4 sources | **2 sources**: YouTube + Google general search |
| Max Iterations | 10 | **No limit** - continues until threshold |
| Notion Integration | Custom API | **Notion MCP** (Model Context Protocol) |
| Twitter/Instagram | Included | **Skipped** for now |

---

# PART 1: SYSTEM ARCHITECTURE OVERVIEW

## 1.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SELF-EVOLVING VIDEO SCRIPT SYSTEM                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE 1: TOPIC DISCOVERY                          │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │   ┌──────────────────┐     ┌──────────────────┐                    │   │
│  │   │ YouTube Data API │     │ Google Search    │                    │   │
│  │   │ (Trending)       │     │ (What's trending │                    │   │
│  │   │                  │     │  in Pakistan)    │                    │   │
│  │   └────────┬─────────┘     └────────┬─────────┘                    │   │
│  │            │                        │                               │   │
│  │            └────────────┬───────────┘                               │   │
│  │                         │                                           │   │
│  │                         ▼                                           │   │
│  │            ┌────────────────────────┐                              │   │
│  │            │ YouTube Analytics API  │                              │   │
│  │            │ (Your video performance)│                             │   │
│  │            │ → Content Gap Analysis  │                             │   │
│  │            └────────────┬───────────┘                              │   │
│  │                         │                                           │   │
│  │                         ▼                                           │   │
│  │            ┌────────────────────────┐                              │   │
│  │            │ Topic Viability Scorer │                              │   │
│  │            │ (17 Criteria Check)    │                              │   │
│  │            └────────────┬───────────┘                              │   │
│  │                         │                                           │   │
│  └─────────────────────────┼───────────────────────────────────────────┘   │
│                            │                                                │
│                            ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 COMPLEXITY ASSESSMENT                                 │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │   Low Complexity    ──────────►  SHORT VIDEO (3-5 min)              │   │
│  │   Medium Complexity ──────────►  MEDIUM VIDEO (8-12 min)            │   │
│  │   High Complexity   ──────────►  LONG VIDEO (15+ min)               │   │
│  │                                                                      │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    USER APPROVAL GATE                                 │   │
│  │                    (Show topic, get approval)                         │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ╔═════════════════════════════════════════════════════════════════════╗   │
│  ║                                                                      ║   │
│  ║              SELF-EVOLVING SCRIPT GENERATION LOOP                    ║   │
│  ║              (Karpathy Auto-Research Methodology)                    ║   │
│  ║                                                                      ║   │
│  ║   ┌──────────────────────────────────────────────────────────────┐  ║   │
│  ║   │ ITERATION N                                                   │  ║   │
│  ║   │                                                               │  ║   │
│  ║   │  1. DEEP RESEARCH                                             │  ║   │
│  ║   │     ├── Web search via FreeRouter                             │  ║   │
│  ║   │     ├── Source aggregation                                    │  ║   │
│  ║   │     └── Fact extraction                                       │  ║   │
│  ║   │                                                               │  ║   │
│  ║   │  2. SCRIPT GENERATION                                         │  ║   │
│  ║   │     ├── Johnny Harris style application                       │  ║   │
│  ║   │     ├── Dual-column format                                    │  ║   │
│  ║   │     └── Duration matching                                     │  ║   │
│  ║   │                                                               │  ║   │
│  ║   │  3. SELF-EVALUATION                                           │  ║   │
│  ║   │     ├── Score against evaluation questions                    │  ║   │
│  ║   │     ├── Identify weak areas                                   │  ║   │
│  ║   │     └── Calculate production readiness %                      │  ║   │
│  ║   │                                                               │  ║   │
│  ║   │  4. DECISION POINT                                            │  ║   │
│  ║   │     ├── Score ≥ 85%? ───────────────► EXIT LOOP ✓             │  ║   │
│  ║   │     └── Score < 85%?  ───────────────► CONTINUE               │  ║   │
│  ║   │                                                               │  ║   │
│  ║   │  5. PROMPT ADJUSTMENT                                         │  ║   │
│  ║   │     ├── Analyze weak areas                                    │  ║   │
│  ║   │     ├── Modify prompt strategy                                │  ║   │
│  ║   │     └── INCREMENT ITERATION (N+1)                             │  ║   │
│  ║   │                                                               │  ║   │
│  ║   └──────────────────────────────────────────────────────────────┘  ║   │
│  ║                                                                      ║   │
│  ║   NOTE: NO MAXIMUM ITERATION LIMIT                                   ║   │
│  ║         Loop continues until 85% threshold is met                    ║   │
│  ║                                                                      ║   │
│  ╚══════════════════════════════════════════════════════════════════════╝   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    LOCALIZATION (Pakistan Audience)                  │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    OUTPUT TO NOTION (via MCP)                        │   │
│  │                    - Complete script                                 │   │
│  │                    - Evaluation log                                  │   │
│  │                    - Production notes                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# PART 2: MULTI-PROVIDER FREEROUTER SYSTEM

## 2.1 Provider Summary

### Existing Providers (Already Implemented)

| Provider | Priority | Type | Free Tier | Status |
|----------|----------|------|-----------|--------|
| Ollama | 10 | Local | Unlimited | ✓ Existing |
| **Groq** | 20 | Cloud | Yes | ✓ Existing |
| OpenRouter | 30 | Cloud | Yes | ✓ Existing |
| Together | 40 | Cloud | Limited | ✓ Existing |
| DeepInfra | 50 | Cloud | Pay/use | ✓ Existing |
| OpenAI | 60 | Cloud | No | ✓ Existing |
| Anthropic | 70 | Cloud | No | ✓ Existing |

### New Providers to Add

| Provider | Priority | Free Tier | API Format | Key Needed |
|----------|----------|-----------|------------|------------|
| **Mistral** | 35 | Yes | OpenAI-compatible | `MISTRAL_API_KEY` |
| **SambaNova** | 45 | Yes | OpenAI-compatible | `SAMBANOVA_API_KEY` |
| **Cerebras** | 55 | Yes | OpenAI-compatible | `CEREBRAS_API_KEY` |
| **GitHub Models** | 65 | Yes | OpenAI-compatible | `GITHUB_TOKEN` |
| **APIFreeLLM** | 75 | Yes | **Custom** (not OpenAI-compatible) | `APIFREELLM_API_KEY` |
| **z.ai** | 80 | Yes | OpenAI-compatible | `ZAI_API_KEY` |
| **Grok (X.AI)** | 85 | Limited | OpenAI-compatible | `GROK_API_KEY` |

## 2.2 APIFreeLLM Implementation (Special Case)

APIFreeLLM uses a **non-OpenAI-compatible** API format:

### API Specification

```
Endpoint: https://apifreellm.com/api/v1/chat
Method: POST
Headers:
  Content-Type: application/json
  Authorization: Bearer YOUR_API_KEY

Request Body:
{
  "message": "Your prompt here",      // ← Note: "message" not "messages"
  "model": "apifreellm"               // Optional, defaults to "apifreellm"
}

Response:
{
  "success": true,
  "response": "AI response text...",
  "tier": "free",
  "features": {
    "unlimited": true,
    "delaySeconds": 25,
    "priorityProcessing": false
  }
}

Rate Limit: 429 → Wait 25 seconds and retry
Context Limit: Free tier 32k tokens
```

### Implementation Strategy

```python
# File: freerouter/src/freerouter/providers.py

class APIFreeLLMAdapter:
    """
    Adapter for APIFreeLLM's non-standard API.
    Converts between OpenAI format and APIFreeLLM format.
    """
    
    API_ENDPOINT = "https://apifreellm.com/api/v1/chat"
    
    async def complete(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> dict:
        """
        Convert OpenAI-style messages to APIFreeLLM format,
        send request, and convert response back.
        """
        # Convert messages to single message string
        combined_message = self._messages_to_string(messages)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.API_ENDPOINT,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json={
                    "message": combined_message,
                    "model": "apifreellm"
                }
            )
            
            if response.status_code == 429:
                # Rate limited - wait 25 seconds
                await asyncio.sleep(25)
                return await self.complete(messages, temperature, max_tokens)
            
            data = response.json()
            
            if not data.get("success"):
                raise RouterError(f"APIFreeLLM error: {data}")
            
            # Convert response to OpenAI format
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": data["response"]
                    },
                    "index": 0,
                    "finish_reason": "stop"
                }],
                "_provider": "apifreellm",
                "_model": "apifreellm"
            }
    
    def _messages_to_string(self, messages: list[dict]) -> str:
        """Convert OpenAI messages array to single string."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"[SYSTEM]: {content}")
            elif role == "user":
                parts.append(f"[USER]: {content}")
            elif role == "assistant":
                parts.append(f"[ASSISTANT]: {content}")
        return "\n\n".join(parts)
```

## 2.3 z.ai Implementation

z.ai uses OpenAI-compatible API format:

```python
# File: freerouter/src/freerouter/providers.py

ProviderDefinition(
    name="zai",
    display_name="Z.AI (GLM Models)",
    provider_type=ProviderType.CLOUD,
    env_key="ZAI_API_KEY",
    base_url="https://api.z.ai/v1",  # OpenAI-compatible endpoint
    health_url="https://api.z.ai/v1/models",
    signup_url="https://docs.z.ai/",
    priority=80,
)

# Default model: GLM-4.7 series
DEFAULT_MODELS["zai"] = "glm-4.7-flash"
```

## 2.4 Provider Definitions to Add

```python
# Add to KNOWN_PROVIDERS list in providers.py:

# ─── Mistral AI ─────────────────────────────────────────────────────────
ProviderDefinition(
    name="mistral",
    display_name="Mistral AI",
    provider_type=ProviderType.CLOUD,
    env_key="MISTRAL_API_KEY",
    base_url="https://api.mistral.ai/v1",
    health_url="https://api.mistral.ai/v1/models",
    signup_url="https://console.mistral.ai/",
    priority=35,
),

# ─── SambaNova ──────────────────────────────────────────────────────────
ProviderDefinition(
    name="sambanova",
    display_name="SambaNova Cloud",
    provider_type=ProviderType.CLOUD,
    env_key="SAMBANOVA_API_KEY",
    base_url="https://api.sambanova.ai/v1",
    health_url="https://api.sambanova.ai/v1/models",
    signup_url="https://cloud.sambanova.ai/",
    priority=45,
),

# ─── Cerebras ───────────────────────────────────────────────────────────
ProviderDefinition(
    name="cerebras",
    display_name="Cerebras AI",
    provider_type=ProviderType.CLOUD,
    env_key="CEREBRAS_API_KEY",
    base_url="https://api.cerebras.ai/v1",
    health_url="https://api.cerebras.ai/v1/models",
    signup_url="https://cloud.cerebras.ai/",
    priority=55,
),

# ─── GitHub Models ──────────────────────────────────────────────────────
ProviderDefinition(
    name="github",
    display_name="GitHub Models",
    provider_type=ProviderType.CLOUD,
    env_key="GITHUB_TOKEN",
    base_url="https://models.inference.ai.azure.com",
    health_url="https://models.inference.ai.azure.com/models",
    signup_url="https://github.com/settings/tokens",
    priority=65,
),

# ─── APIFreeLLM (Special - Non-OpenAI format) ───────────────────────────
ProviderDefinition(
    name="apifreellm",
    display_name="APIFreeLLM",
    provider_type=ProviderType.CLOUD,
    env_key="APIFREELLM_API_KEY",
    base_url="https://apifreellm.com/api/v1",
    health_url="https://apifreellm.com/api/v1/status",
    signup_url="https://apifreellm.com/en/api-access",
    priority=75,
    requires_adapter=True,  # Flag for special handling
),

# ─── z.ai ───────────────────────────────────────────────────────────────
ProviderDefinition(
    name="zai",
    display_name="Z.AI (GLM Models)",
    provider_type=ProviderType.CLOUD,
    env_key="ZAI_API_KEY",
    base_url="https://api.z.ai/v1",
    health_url="https://api.z.ai/v1/models",
    signup_url="https://docs.z.ai/",
    priority=80,
),

# ─── Grok (X.AI) ────────────────────────────────────────────────────────
ProviderDefinition(
    name="grok",
    display_name="Grok (X.AI)",
    provider_type=ProviderType.CLOUD,
    env_key="GROK_API_KEY",
    base_url="https://api.x.ai/v1",
    health_url="https://api.x.ai/v1/models",
    signup_url="https://console.x.ai/",
    priority=85,
),

# ─── Updated Default Models ─────────────────────────────────────────────
DEFAULT_MODELS.update({
    "mistral": "mistral-small-latest",
    "sambanova": "Meta-Llama-3.1-8B-Instruct",
    "cerebras": "llama-3.3-70b",
    "github": "gpt-4o-mini",
    "apifreellm": "apifreellm",
    "zai": "glm-4.7-flash",
    "grok": "grok-2-latest",
})
```

## 2.5 Environment Configuration

```bash
# File: freerouter/.env

# =============================================================================
# EXISTING PROVIDERS (Already configured)
# =============================================================================
GROQ_API_KEY=your_groq_key_here
OPENROUTER_API_KEY=your_openrouter_key_here

# =============================================================================
# NEW PROVIDERS - Add your keys here
# =============================================================================

# Mistral AI - https://console.mistral.ai/
MISTRAL_API_KEY=your_mistral_key_here

# SambaNova - https://cloud.sambanova.ai/
SAMBANOVA_API_KEY=your_sambanova_key_here

# Cerebras - https://cloud.cerebras.ai/
CEREBRAS_API_KEY=your_cerebras_key_here

# GitHub Models - https://github.com/settings/tokens
# Requires 'models:read' scope
GITHUB_TOKEN=your_github_token_here

# APIFreeLLM - https://apifreellm.com/en/api-access
APIFREELLM_API_KEY=your_apifreellm_key_here

# z.ai - https://docs.z.ai/
ZAI_API_KEY=your_zai_key_here

# Grok (X.AI) - https://console.x.ai/
GROK_API_KEY=your_grok_key_here

# =============================================================================
# LOCAL PROVIDER
# =============================================================================
OLLAMA_BASE_URL=http://localhost:11434/v1

# =============================================================================
# YOUTUBE APIS (For Trend Analysis)
# =============================================================================
YOUTUBE_DATA_API_KEY=your_youtube_data_api_key
YOUTUBE_ANALYTICS_API_KEY=your_youtube_analytics_api_key
```

---

# PART 3: TREND ANALYSIS SYSTEM

## 3.1 Simplified Trend Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    TREND ANALYSIS                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   SOURCE 1: YouTube Data API v3                                 │
│   ─────────────────────────────────                             │
│   Purpose: Get trending videos in Pakistan                      │
│   API: youtube.videos.list(chart="mostPopular", region="PK")   │
│   Output: List of trending video titles, categories, views     │
│                                                                  │
│   SOURCE 2: YouTube Analytics API                               │
│   ─────────────────────────────────                             │
│   Purpose: Analyze YOUR video performance                       │
│   API: youtubeAnalytics.reports.query()                        │
│   Output: Your top videos, engagement metrics, gaps            │
│                                                                  │
│   SOURCE 3: Google Search (General)                             │
│   ─────────────────────────────────                             │
│   Query: "what is trending in Pakistan today"                   │
│   Query: "Pakistan trending topics"                             │
│   Query: "latest news Pakistan"                                 │
│   Output: Current trending topics in Pakistan                   │
│                                                                  │
│   ──────────────────────────────────────────────────────────── │
│                                                                  │
│   CROSS-REFERENCE:                                              │
│   - Find topics appearing in multiple sources                   │
│   - Check against your existing content (avoid duplicates)      │
│   - Score by:                                                   │
│     * Trend momentum                                            │
│     * Audience interest                                         │
│     * Content gap potential                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 3.2 Trend Analyzer Implementation

```python
# File: packages/content_factory/trend_analysis/aggregator.py

from googleapiclient.discovery import build
from packages.router.client import RouterClient

class TrendAnalyzer:
    """
    Analyzes trending topics from YouTube and Google Search.
    """
    
    def __init__(self):
        self.youtube_data_key = os.getenv("YOUTUBE_DATA_API_KEY")
        self.youtube_analytics_key = os.getenv("YOUTUBE_ANALYTICS_API_KEY")
        self.router = RouterClient()
    
    async def get_youtube_trends(self, region: str = "PK") -> list[dict]:
        """
        Fetch trending videos from YouTube Data API v3.
        """
        youtube = build("youtube", "v3", developerKey=self.youtube_data_key)
        
        request = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode=region,
            maxResults=50
        )
        response = request.execute()
        
        trends = []
        for item in response.get("items", []):
            trends.append({
                "title": item["snippet"]["title"],
                "category": item["snippet"].get("categoryId"),
                "views": int(item["statistics"].get("viewCount", 0)),
                "source": "youtube_trending"
            })
        
        return trends
    
    async def get_your_video_performance(self) -> list[dict]:
        """
        Analyze your own video performance via YouTube Analytics API.
        Identifies what's working and content gaps.
        """
        youtube_analytics = build(
            "youtubeAnalytics", 
            "v2", 
            developerKey=self.youtube_analytics_key
        )
        
        # Get performance metrics for your channel
        request = youtube_analytics.reports().query(
            ids="channel==MINE",
            metrics="views,averageViewDuration,subscriberStatus",
            dimensions="video",
            sort="-views",
            maxResults=50
        )
        response = request.execute()
        
        # Analyze top performers and identify gaps
        return self._analyze_performance_gaps(response)
    
    async def get_google_trends_pakistan(self) -> list[dict]:
        """
        Search for what's trending in Pakistan using general web search.
        """
        queries = [
            "what is trending in Pakistan today",
            "Pakistan trending topics 2025",
            "latest news Pakistan",
            "Pakistan viral topics"
        ]
        
        results = []
        async with RouterClient() as router:
            for query in queries:
                search_results = await router.web_search(query, num=10)
                for item in search_results:
                    results.append({
                        "topic": item.get("name", ""),
                        "snippet": item.get("snippet", ""),
                        "source": "google_search"
                    })
        
        return self._deduplicate_topics(results)
    
    async def aggregate_trends(self) -> list[AggregatedTrend]:
        """
        Combine all trend sources and score topics.
        """
        # Fetch from all sources
        yt_trends = await self.get_youtube_trends()
        your_videos = await self.get_your_video_performance()
        google_trends = await self.get_google_trends_pakistan()
        
        # Combine and score
        all_topics = []
        
        # YouTube trends get higher weight
        for t in yt_trends:
            all_topics.append({
                "topic": t["title"],
                "source": "youtube_trending",
                "weight": 0.5,
                "views": t.get("views", 0)
            })
        
        # Google trends get medium weight
        for t in google_trends:
            all_topics.append({
                "topic": t["topic"],
                "source": "google_search",
                "weight": 0.3,
                "snippet": t.get("snippet", "")
            })
        
        # Your video gaps inform what NOT to cover again
        covered_topics = [v["title"] for v in your_videos]
        
        # Score and filter
        scored = self._score_and_filter(all_topics, covered_topics)
        
        return sorted(scored, key=lambda x: x["score"], reverse=True)
```

---

# PART 4: SELF-EVOLVING SCRIPT LOOP

## 4.1 Loop Architecture (No Max Iterations)

```python
# File: packages/content_factory/script_generator/evolution_loop.py

class ScriptEvolutionLoop:
    """
    Iterative script generation with self-evaluation.
    Continues until 85% threshold is met - NO MAXIMUM ITERATIONS.
    """
    
    THRESHOLD = 0.85  # 85% production readiness
    
    def __init__(self):
        self.evaluator = SelfEvaluator()
        self.prompt_adjuster = PromptAdjuster()
        self.iteration_count = 0
        self.score_history = []
    
    async def evolve_script(
        self,
        topic: TopicBrief,
        complexity: ComplexityReport,
        research_data: dict
    ) -> DualColumnScript:
        """
        Main evolution loop. Continues until threshold is met.
        """
        
        current_prompt = self._build_initial_prompt(topic, complexity)
        current_script = None
        current_scores = {}
        
        while True:  # No maximum - continues until threshold
            self.iteration_count += 1
            
            print(f"\n{'='*50}")
            print(f"ITERATION {self.iteration_count}")
            print(f"{'='*50}")
            
            # 1. Generate script
            current_script = await self._generate_script(
                current_prompt, 
                research_data,
                complexity
            )
            
            # 2. Self-evaluate
            current_scores = await self.evaluator.evaluate(
                current_script,
                research_data
            )
            
            overall_score = current_scores["overall_score"]
            self.score_history.append(overall_score)
            
            print(f"Score: {overall_score*100:.1f}%")
            
            # 3. Check threshold
            if overall_score >= self.THRESHOLD:
                print(f"\n✓ THRESHOLD MET after {self.iteration_count} iterations")
                return current_script
            
            # 4. Analyze weak areas
            weak_areas = self._identify_weak_areas(current_scores)
            print(f"Weak areas: {weak_areas}")
            
            # 5. Adjust prompt
            current_prompt = self.prompt_adjuster.adjust(
                current_prompt,
                weak_areas,
                self.iteration_count,
                current_script
            )
            
            # 6. Optional: Check for stagnation (but don't stop, just warn)
            if self._check_stagnation():
                print("⚠ Stagnation detected - trying different strategy")
                current_prompt = self.prompt_adjuster.try_different_strategy(
                    current_prompt,
                    weak_areas
                )
    
    def _check_stagnation(self) -> bool:
        """Check if scores are not improving."""
        if len(self.score_history) < 3:
            return False
        
        recent = self.score_history[-3:]
        return (max(recent) - min(recent)) < 0.02
```

## 4.2 Self-Evaluation Questions

```python
# File: packages/content_factory/evaluation/questions.py

EVALUATION_QUESTIONS = {
    # ─── HOOK EVALUATION (25%) ─────────────────────────────────────────
    "hook": {
        "weight": 0.25,
        "questions": {
            "H1": {
                "text": "Does the hook create immediate curiosity within the first 5 seconds?",
                "weight": 0.10
            },
            "H2": {
                "text": "Is the mainstream assumption clearly stated?",
                "weight": 0.08
            },
            "H3": {
                "text": "Does the visual anchor appear early enough?",
                "weight": 0.07
            }
        }
    },
    
    # ─── NARRATIVE EVALUATION (30%) ─────────────────────────────────────
    "narrative": {
        "weight": 0.30,
        "questions": {
            "N1": {
                "text": "Does each section have a clear purpose?",
                "weight": 0.08
            },
            "N2": {
                "text": "Is the hidden mechanism explained visually?",
                "weight": 0.10
            },
            "N3": {
                "text": "Are transitions smooth between sections?",
                "weight": 0.06
            },
            "N4": {
                "text": "Is the pacing appropriate for the complexity level?",
                "weight": 0.06
            }
        }
    },
    
    # ─── EVIDENCE EVALUATION (25%) ──────────────────────────────────────
    "evidence": {
        "weight": 0.25,
        "questions": {
            "E1": {
                "text": "Is every claim supported by research?",
                "weight": 0.10
            },
            "E2": {
                "text": "Are sources credible and current?",
                "weight": 0.08
            },
            "E3": {
                "text": "Is the smoking gun visually compelling?",
                "weight": 0.07
            }
        }
    },
    
    # ─── AUDIENCE CONNECTION (20%) ──────────────────────────────────────
    "audience": {
        "weight": 0.20,
        "questions": {
            "A1": {
                "text": "Does this matter to Pakistani audience?",
                "weight": 0.08
            },
            "A2": {
                "text": "Is local context properly integrated?",
                "weight": 0.06
            },
            "A3": {
                "text": "Does it explain 'why things are this way'?",
                "weight": 0.06
            }
        }
    }
}
```

## 4.3 Prompt Adjustment Strategy

```python
# File: packages/content_factory/script_generator/prompt_adjuster.py

class PromptAdjuster:
    """
    Adjusts prompts based on evaluation results.
    Uses different strategies to improve weak areas.
    """
    
    IMPROVEMENT_HINTS = {
        "H1": """
The hook is not creating enough curiosity. Try:
- Start with a provocative question
- Use a surprising statistic
- Create a knowledge gap that demands to be filled
- Use visual contrast to create intrigue
""",
        "H2": """
The mainstream assumption is not clear. Try:
- Explicitly state: "Most people think X, but..."
- Use a common belief as the contrast
- Make the gap between belief and reality stark
""",
        "N2": """
The hidden mechanism is not explained visually enough. Try:
- Add more B-roll descriptions
- Include animation suggestions
- Use diagrams and visual metaphors
- Show rather than tell
""",
        "E1": """
Claims lack supporting evidence. Try:
- Add specific source citations
- Include data points with attribution
- Reference the research more explicitly
- Use quotes from credible sources
""",
        "A1": """
Not enough connection to Pakistani audience. Try:
- Add local examples and references
- Connect to Pakistani current events
- Use locally relevant analogies
- Address Pakistani-specific implications
""",
    }
    
    def adjust(
        self,
        current_prompt: str,
        weak_areas: list[str],
        iteration: int,
        previous_script: DualColumnScript
    ) -> str:
        """
        Generate an adjusted prompt targeting weak areas.
        """
        hints = []
        for area in weak_areas:
            hint = self.IMPROVEMENT_HINTS.get(area, "")
            if hint:
                hints.append(f"### Focus on {area}:{hint}")
        
        adjustment_block = "\n".join(hints)
        
        return f"""
{current_prompt}

═══════════════════════════════════════════════════════════════
ITERATION {iteration} REFINEMENT
═══════════════════════════════════════════════════════════════

Previous attempt scored low on: {', '.join(weak_areas)}

SPECIFIC IMPROVEMENTS NEEDED:
{adjustment_block}

CRITICAL: You MUST address these weaknesses. Score must reach 85%.

Previous script for reference (do NOT repeat the same mistakes):
{previous_script.to_summary()[:500]}...
"""
    
    def try_different_strategy(
        self,
        current_prompt: str,
        weak_areas: list[str]
    ) -> str:
        """
        When stagnation is detected, try a completely different approach.
        """
        strategies = [
            self._strategy_change_angle,
            self._strategy_simplify_structure,
            self._strategy_add_emotional_layer,
            self._strategy_focus_on_visuals,
        ]
        
        strategy = strategies[len(weak_areas) % len(strategies)]
        return strategy(current_prompt, weak_areas)
```

---

# PART 5: COMPLEXITY-BASED DURATION

## 5.1 Complexity Factors

| Factor | Weight | Low (1) | Medium (2) | High (3) |
|--------|--------|---------|------------|----------|
| Hidden Mechanisms | 25% | Single clear mechanism | Multiple related | Complex interconnected |
| Visual Asset Availability | 20% | Abundant B-roll | Some available | Requires custom creation |
| Audience Knowledge Gap | 25% | Familiar territory | Partially known | Completely new |
| Emotional Depth | 15% | Informational | Moderate journey | Deep resonance |
| Source Complexity | 15% | Few reliable sources | Multiple synthesis | Extensive research |

## 5.2 Duration Mapping

| Score Range | Duration | Structure |
|-------------|----------|-----------|
| 1.0 - 1.6 | **SHORT (3-5 min)** | hook → reveal → conclusion |
| 1.6 - 2.3 | **MEDIUM (8-12 min)** | hook → investigation → reveal → conclusion |
| 2.3 - 3.0 | **LONG (15+ min)** | hook → deep investigation → multiple reveals → conclusion |

---

# PART 6: NOTION OUTPUT (via MCP)

## 6.1 Notion MCP Integration

The user will use **Notion's official MCP (Model Context Protocol)** for output.

```
┌─────────────────────────────────────────────────────────────────┐
│                    NOTION OUTPUT FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Script Ready (≥85%)                                           │
│          │                                                       │
│          ▼                                                       │
│   ┌─────────────────────┐                                       │
│   │ Format for Notion   │                                       │
│   │ - Title             │                                       │
│   │ - Overview section  │                                       │
│   │ - Dual-column table │                                       │
│   │ - Research sources  │                                       │
│   │ - Evaluation log    │                                       │
│   │ - Production notes  │                                       │
│   └──────────┬──────────┘                                       │
│              │                                                   │
│              ▼                                                   │
│   ┌─────────────────────┐                                       │
│   │ Notion MCP          │                                       │
│   │ (User's setup)      │                                       │
│   └──────────┬──────────┘                                       │
│              │                                                   │
│              ▼                                                   │
│   ┌─────────────────────┐                                       │
│   │ Notion Page Created │                                       │
│   │ - Linked back to AI │                                       │
│   │ - Ready for review  │                                       │
│   └─────────────────────┘                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 6.2 Output Format

```python
# File: packages/content_factory/output/notion_formatter.py

class NotionOutputFormatter:
    """
    Formats completed scripts for Notion MCP output.
    """
    
    def format_script(self, script: DualColumnScript) -> dict:
        """
        Create Notion-compatible structure.
        """
        return {
            "title": script.adapted_title,
            "blocks": [
                # Overview Section
                {
                    "type": "heading_2",
                    "text": "📋 Overview"
                },
                {
                    "type": "paragraph",
                    "text": f"""
Topic: {script.topic_statement}
Big Question: {script.big_question}
Duration: {script.duration_category}
Production Readiness: {script.production_readiness_score}%
Iterations: {script.iteration_count}
"""
                },
                
                # Dual-Column Script
                {
                    "type": "heading_2",
                    "text": "📝 Dual-Column Script"
                },
                self._create_dual_column_table(script.entries),
                
                # Research Sources
                {
                    "type": "heading_2",
                    "text": "🔍 Research Sources"
                },
                *self._format_sources(script.sources),
                
                # Evaluation Log
                {
                    "type": "heading_2",
                    "text": "📊 Self-Evaluation Log"
                },
                *self._format_evaluation_log(script.evaluation_history),
                
                # Production Checklist
                {
                    "type": "heading_2",
                    "text": "✅ Production Checklist"
                },
                {
                    "type": "to_do",
                    "items": [
                        "Script approved",
                        "Research verified",
                        "Visuals sourced",
                        "Ready for production"
                    ]
                }
            ]
        }
```

---

# PART 7: FILE STRUCTURE

## 7.1 New Files to Create

```
AI-Orchestration/
├── freerouter/
│   └── src/freerouter/
│       ├── providers.py              # MODIFY: Add 7 new providers
│       ├── adapters/
│       │   ├── __init__.py
│       │   └── apifreellm.py         # NEW: APIFreeLLM adapter
│       └── router.py                 # MODIFY: Handle non-standard APIs
│
├── packages/
│   └── content_factory/
│       ├── trend_analysis/
│       │   ├── __init__.py
│       │   ├── aggregator.py         # NEW: Trend aggregation
│       │   ├── youtube_trends.py     # NEW: YouTube API integration
│       │   └── google_trends.py      # NEW: Google search trends
│       │
│       ├── script_generator/
│       │   ├── __init__.py
│       │   ├── jh_style.py           # NEW: Johnny Harris patterns
│       │   ├── dual_column.py        # NEW: Dual-column generator
│       │   ├── evolution_loop.py     # NEW: Main evolution loop
│       │   └── prompt_adjuster.py    # NEW: Prompt refinement
│       │
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── self_evaluator.py     # NEW: Self-evaluation engine
│       │   └── questions.py          # NEW: Evaluation questions
│       │
│       ├── complexity/
│       │   ├── __init__.py
│       │   └── assessor.py           # NEW: Complexity assessment
│       │
│       └── output/
│           ├── __init__.py
│           └── notion_formatter.py   # NEW: Notion MCP output
│
├── scripts/
│   └── generate_video_script.py      # NEW: Main entry point
│
└── tests/
    ├── test_new_providers.py         # NEW: Provider tests
    ├── test_evolution_loop.py        # NEW: Loop tests
    └── test_trend_analysis.py        # NEW: Trend tests
```

## 7.2 Files to Modify

| File | Changes |
|------|---------|
| `freerouter/providers.py` | Add 7 new provider definitions |
| `freerouter/router.py` | Handle APIFreeLLM's non-standard API |
| `packages/content_factory/topic_finder/finder.py` | Integrate trend analysis |
| `scripts/auto_production.py` | Use new evolution loop |

---

# PART 8: IMPLEMENTATION PHASES

## Phase 1: Provider Infrastructure (Days 1-2)
- [ ] Add Mistral, SambaNova, Cerebras, GitHub Models (OpenAI-compatible)
- [ ] Add z.ai and Grok (X.AI)
- [ ] Create APIFreeLLM adapter for non-standard API
- [ ] Update .env.example with all new key slots
- [ ] Test each provider individually
- [ ] Test failover chain

## Phase 2: Trend Analysis (Day 3)
- [ ] YouTube Data API v3 integration
- [ ] YouTube Analytics API integration
- [ ] Google Search trend queries
- [ ] Trend aggregation and scoring

## Phase 3: Self-Evaluation Engine (Days 4-5)
- [ ] Create evaluation questions database
- [ ] Implement self-evaluator
- [ ] Build prompt adjustment logic
- [ ] Test iterative loop

## Phase 4: Script Generation (Days 6-7)
- [ ] Johnny Harris style templates
- [ ] Dual-column script generator
- [ ] Complexity assessment
- [ ] Integration with evolution loop

## Phase 5: Output & Integration (Day 8)
- [ ] Notion MCP formatter
- [ ] End-to-end testing
- [ ] Performance optimization

## Phase 6: Deployment (Day 9)
- [ ] Local testing
- [ ] Oracle Cloud deployment
- [ ] Monitoring setup

---

# PART 9: SUMMARY OF KEY DECISIONS

| Decision | Choice |
|----------|--------|
| **Loop Iterations** | NO MAXIMUM - continues until 85% threshold |
| **Trend Sources** | YouTube Data API + Google Search only |
| **Twitter/Instagram** | SKIPPED for now |
| **Notion Integration** | Via Notion MCP (user's setup) |
| **APIFreeLLM** | Custom adapter (non-OpenAI format) |
| **Duration** | Complexity-based: Short → Medium → Long |

---

*Plan Version: 3.0*
*Status: Ready for User Approval*
*Next Step: Implement after user confirms plan*
