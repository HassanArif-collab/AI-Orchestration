# Implementation Plan: Multi-Provider FreeRouter & Video Script Generation

**Branch:** `Explaining-FinalRefactoring`
**Date:** 2025-03-25

---

## Executive Summary

This document outlines the plan to:
1. Expand the FreeRouter system to support multiple free-tier AI providers
2. Implement automatic failover when providers reach rate limits
3. Create a complete video script generation workflow from approved topics

---

## Part 1: Multi-Provider FreeRouter System

### 1.1 Current State Analysis

**Existing Providers (in `providers.py`):**
| Provider | Priority | Type | Status |
|----------|----------|------|--------|
| Ollama | 10 | Local | Implemented |
| Groq | 20 | Cloud | Implemented |
| OpenRouter | 30 | Cloud | Implemented |
| Together | 40 | Cloud | Implemented |
| DeepInfra | 50 | Cloud | Implemented |
| OpenAI | 60 | Cloud | Implemented |
| Anthropic | 70 | Cloud | Implemented |

**Missing Providers (User's Requirements):**
| Provider | Free Tier | API Format | Notes |
|----------|-----------|------------|-------|
| Grok (X.AI) | Limited | OpenAI-compatible | x.ai API |
| Mistral | Yes | OpenAI-compatible | mistral.ai |
| APIFreeLlm | Yes | OpenAI-compatible | Needs research |
| z.ai | Yes | Custom/OpenAI | Needs research |
| Sambanova | Yes | OpenAI-compatible | sambanova.ai |
| Cerebras | Yes | OpenAI-compatible | cerebras.ai |
| GitHub Models | Yes | OpenAI-compatible | models.githubusercontent.com |

### 1.2 Implementation Plan: Provider Additions

#### File: `freerouter/src/freerouter/providers.py`

**Task 1.2.1: Add Grok (X.AI) Provider**
```python
ProviderDefinition(
    name="grok",
    display_name="Grok (X.AI)",
    provider_type=ProviderType.CLOUD,
    env_key="GROK_API_KEY",
    base_url="https://api.x.ai/v1",
    health_url="https://api.x.ai/v1/models",
    signup_url="https://console.x.ai/",
    priority=25,  # Between Groq and OpenRouter
)
# Default model: "grok-2-latest" or "grok-beta"
```

**Task 1.2.2: Add Mistral Provider**
```python
ProviderDefinition(
    name="mistral",
    display_name="Mistral AI",
    provider_type=ProviderType.CLOUD,
    env_key="MISTRAL_API_KEY",
    base_url="https://api.mistral.ai/v1",
    health_url="https://api.mistral.ai/v1/models",
    signup_url="https://console.mistral.ai/",
    priority=35,
)
# Default model: "mistral-small-latest" (free tier)
```

**Task 1.2.3: Add Sambanova Provider**
```python
ProviderDefinition(
    name="sambanova",
    display_name="SambaNova Cloud",
    provider_type=ProviderType.CLOUD,
    env_key="SAMBANOVA_API_KEY",
    base_url="https://api.sambanova.ai/v1",
    health_url="https://api.sambanova.ai/v1/models",
    signup_url="https://cloud.sambanova.ai/",
    priority=45,
)
# Default model: "Meta-Llama-3.1-8B-Instruct"
```

**Task 1.2.4: Add Cerebras Provider**
```python
ProviderDefinition(
    name="cerebras",
    display_name="Cerebras AI",
    provider_type=ProviderType.CLOUD,
    env_key="CEREBRAS_API_KEY",
    base_url="https://api.cerebras.ai/v1",
    health_url="https://api.cerebras.ai/v1/models",
    signup_url="https://cloud.cerebras.ai/",
    priority=55,
)
# Default model: "llama-3.3-70b"
```

**Task 1.2.5: Add GitHub Models Provider**
```python
ProviderDefinition(
    name="github",
    display_name="GitHub Models",
    provider_type=ProviderType.CLOUD,
    env_key="GITHUB_TOKEN",
    base_url="https://models.inference.ai.azure.com",
    health_url="https://models.inference.ai.azure.com/models",
    signup_url="https://github.com/settings/tokens",
    priority=65,
)
# Default model: "gpt-4o-mini" (free tier available)
```

**Task 1.2.6: Research & Add APIFreeLlm and z.ai**
- Need to research API endpoints and authentication methods
- Add once API documentation is located

### 1.3 Implementation Plan: Rate Limit Handling

#### File: `freerouter/src/freerouter/providers.py`

**Current Behavior:**
- Tracks `x-ratelimit-remaining-requests` headers
- Auto-resets hard limits after 60 seconds
- Soft limit threshold at 90%

**Enhancements Needed:**

**Task 1.3.1: Add Provider-Specific Rate Limits**
```python
@dataclass
class ProviderDefinition:
    # ... existing fields ...
    daily_request_limit: int = 0  # 0 = unknown/unlimited
    daily_token_limit: int = 0
    rate_limit_reset_seconds: int = 60  # Per-provider reset time
```

**Task 1.3.2: Add Free Tier Quota Tracking**
```python
@dataclass
class ProviderUsage:
    # ... existing fields ...
    daily_requests_used: int = 0
    daily_tokens_used: int = 0
    quota_reset_time: float = 0.0  # When daily quota resets
```

**Task 1.3.3: Provider Health Status Endpoint**
- Add `/api/providers/detailed-status` endpoint
- Show: quota remaining, estimated reset time, health status

### 1.4 Implementation Plan: Smart Routing

#### File: `freerouter/src/freerouter/router.py`

**Task 1.4.1: Task-Based Provider Selection**
```python
class TaskType(Enum):
    SIMPLE_CHAT = "simple_chat"
    CODING = "coding"
    REASONING = "reasoning"
    CREATIVE = "creative"
    VIDEO_SCRIPT = "video_script"  # New!
    RESEARCH = "research"          # New!

PROVIDER_TASK_AFFINITY = {
    "groq": [TaskType.SIMPLE_CHAT, TaskType.CODING],
    "openrouter": [TaskType.VIDEO_SCRIPT, TaskType.RESEARCH],
    "mistral": [TaskType.CREATIVE, TaskType.REASONING],
    # ...
}
```

**Task 1.4.2: Video Script Generation Routing**
- Route script generation to providers with:
  - Long context windows
  - Good creative writing capabilities
  - Lower cost per token

### 1.5 Environment Configuration

#### File: `freerouter/.env.example`

**Task 1.5.1: Update .env.example Template**
```bash
# =============================================================================
# FREE TIER API KEYS (Add at least one)
# =============================================================================

# OpenRouter - https://openrouter.ai/keys
OPENROUTER_API_KEY=

# Groq (Fast Free Inference) - https://console.groq.com/keys
GROQ_API_KEY=

# Grok (X.AI) - https://console.x.ai/
GROK_API_KEY=

# Mistral AI - https://console.mistral.ai/
MISTRAL_API_KEY=

# SambaNova - https://cloud.sambanova.ai/
SAMBANOVA_API_KEY=

# Cerebras - https://cloud.cerebras.ai/
CEREBRAS_API_KEY=

# GitHub Models - https://github.com/settings/tokens
# Requires 'models:read' scope
GITHUB_TOKEN=

# Ollama (Local) - No key needed
OLLAMA_BASE_URL=http://localhost:11434/v1

# =============================================================================
# OPTIONAL PAID PROVIDERS
# =============================================================================

# OpenAI - https://platform.openai.com/api-keys
# OPENAI_API_KEY=

# Anthropic - https://console.anthropic.com/
# ANTHROPIC_API_KEY=
```

---

## Part 2: Video Script Generation Workflow

### 2.1 Current State Analysis

**Existing Components:**
1. `TopicFinderAgent` - Finds topics, scores viability (17 criteria)
2. `stage4_script.py` - Generates dual-column scripts
3. `auto_production.py` - Automated production loop
4. Pipeline stages: Research → Script Writing → Visual Planning → SEO → Publish

**Gap Analysis:**
- System exists but needs:
  - Connection to trend data sources
  - Content gap analysis
  - Johnny Harris style script templates
  - Local audience adaptation for Pakistan

### 2.2 Implementation Plan: Complete Script Generation Pipeline

#### Phase A: Topic Discovery Enhancement

**File: `packages/content_factory/topic_finder/trend_analyzer.py` (NEW)**

**Task 2.2.1: Create Trend Analyzer**
```python
class TrendAnalyzer:
    """Analyzes trending topics from multiple sources."""
    
    sources = [
        "google_trends",      # Via web search
        "youtube_trending",   # YouTube API
        "twitter_trends",     # X/Twitter API
        "reddit_hot",         # Reddit API
    ]
    
    async def get_trending_topics(
        self, 
        region: str = "PK",
        category: str = "news"
    ) -> list[TrendingTopic]:
        """Fetch trending topics for region."""
        pass
    
    async def analyze_content_gap(
        self,
        topic: str,
        existing_content: list[str]
    ) -> ContentGapReport:
        """Find gaps in existing content coverage."""
        pass
```

**Task 2.2.2: Integrate with TopicFinderAgent**
- Add trend data to topic generation prompt
- Score topics based on trend momentum
- Flag time-sensitive topics

#### Phase B: Johnny Harris Style Script Generator

**File: `packages/content_factory/script_generator/jh_style.py` (NEW)**

**Task 2.2.3: Create JH Style Templates**
```python
JOHNNY_HARRIS_PATTERNS = {
    "hook_patterns": [
        "The mainstream narrative about {topic} is wrong. Here's what's really happening.",
        "Everyone thinks {assumption}. But I found something that changes everything.",
        "This {object} tells a story nobody's talking about.",
    ],
    "structural_elements": {
        "visual_anchor": "Physical object/location that grounds the story",
        "hidden_mechanism": "The invisible system driving the story",
        "smoking_gun": "Document/data that proves the thesis",
        "emotional_core": "Human impact that resonates with audience",
    },
    "pacing": {
        "hook_duration": "15-30 seconds",
        "investigation_build": "2-3 minutes",
        "reveal_moment": "30-60 seconds",
        "conclusion": "30-45 seconds",
    }
}

class JHScriptGenerator:
    """Generates Johnny Harris style video scripts."""
    
    async def generate_script(
        self,
        topic: TopicBrief,
        research_data: dict,
        duration_minutes: float = 8.0
    ) -> DualColumnScript:
        """Generate production-ready script."""
        pass
    
    async def adapt_for_local_audience(
        self,
        script: DualColumnScript,
        target_region: str = "Pakistan"
    ) -> DualColumnScript:
        """Adapt script for local audience."""
        pass
```

**Task 2.2.4: Dual-Column Script Format**
```
| Time  | Narration (Left Column)      | Visual Direction (Right Column) |
|-------|------------------------------|--------------------------------|
| 0:00  | "Everyone thinks X is..."    | B-Roll: [Specific visual]      |
| 0:15  | "But I found this document..."| Close-up: [Document/Map]       |
| 0:45  | "Here's what's really..."    | Animation: [Mechanism diagram] |
```

#### Phase C: Complete Workflow Script

**File: `scripts/generate_video_script.py` (NEW)**

**Task 2.2.5: Create Standalone Script Generator**
```python
#!/usr/bin/env python3
"""
Standalone video script generator.

Usage:
    python scripts/generate_video_script.py --topic "Pakistan economic crisis"
    python scripts/generate_video_script.py --trend
    python scripts/generate_video_script.py --gap --genre "current_situation"
"""

async def main():
    # 1. Topic Discovery
    if args.trend:
        topics = await trend_analyzer.get_trending_topics()
    elif args.gap:
        topics = await content_gap_analyzer.find_gaps(args.genre)
    else:
        topics = [args.topic]
    
    # 2. Topic Approval
    selected_topic = await present_topics_for_approval(topics)
    
    # 3. Deep Research
    research = await deep_research(selected_topic)
    
    # 4. Script Generation
    script = await jh_generator.generate_script(selected_topic, research)
    
    # 5. Local Adaptation
    adapted_script = await jh_generator.adapt_for_local_audience(script)
    
    # 6. Output
    save_script(adapted_script, output_format="markdown")
```

### 2.3 Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    VIDEO SCRIPT GENERATION                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                                               │
│  │ INPUT SOURCE │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│    ┌────┴────┬──────────────┐                                   │
│    ▼         ▼              ▼                                   │
│ ┌──────┐ ┌────────┐ ┌────────────┐                             │
│ │Trend │ │ Content│ │ Manual     │                             │
│ │Data  │ │ Gap    │ │ Topic      │                             │
│ └──┬───┘ └───┬────┘ └─────┬──────┘                             │
│    │         │            │                                      │
│    └─────────┴────────────┘                                      │
│              │                                                   │
│              ▼                                                   │
│    ┌─────────────────────┐                                      │
│    │  Topic Viability    │                                      │
│    │  Scoring (17 tests) │                                      │
│    └──────────┬──────────┘                                      │
│               │                                                  │
│        ┌──────┴──────┐                                          │
│        ▼             ▼                                          │
│   ┌─────────┐  ┌──────────┐                                    │
│   │ Tier 1  │  │ Reject & │                                    │
│   │ Pass    │  │ Retry    │                                    │
│   └────┬────┘  └──────────┘                                    │
│        │                                                        │
│        ▼                                                        │
│   ┌─────────────────┐                                          │
│   │  USER APPROVAL  │  ◄── Show topic, ask to proceed          │
│   └────────┬────────┘                                          │
│            │                                                    │
│            ▼                                                    │
│   ┌─────────────────┐      ┌─────────────────┐                 │
│   │  DEEP RESEARCH  │─────►│  FreeRouter     │                 │
│   │  (Web Search +  │      │  (Multi-Provider│                 │
│   │   LLM Synthesis)│      │   Failover)     │                 │
│   └────────┬────────┘      └─────────────────┘                 │
│            │                                                    │
│            ▼                                                    │
│   ┌─────────────────┐                                          │
│   │ SCRIPT GEN      │                                          │
│   │ (JH Style +     │                                          │
│   │  Dual-Column)   │                                          │
│   └────────┬────────┘                                          │
│            │                                                    │
│            ▼                                                    │
│   ┌─────────────────┐                                          │
│   │ LOCALIZATION    │                                          │
│   │ (Pakistan       │                                          │
│   │  Audience)      │                                          │
│   └────────┬────────┘                                          │
│            │                                                    │
│            ▼                                                    │
│   ┌─────────────────┐                                          │
│   │ OUTPUT          │                                          │
│   │ - Markdown      │                                          │
│   │ - JSON          │                                          │
│   │ - Notion Page   │                                          │
│   └─────────────────┘                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 3: Testing & Deployment

### 3.1 Local Testing Plan

**Task 3.1.1: FreeRouter Unit Tests**
- Test each new provider connection
- Test failover logic
- Test rate limit handling

**Task 3.1.2: Script Generation Tests**
- Test topic discovery
- Test script generation with mock data
- Test localization

**Task 3.1.3: Integration Tests**
- Full pipeline test with real API calls
- Measure cost per script generation
- Verify output quality

### 3.2 Oracle Cloud Deployment

**Task 3.2.1: Environment Setup**
- VM configuration
- Docker installation
- Environment variables

**Task 3.2.2: Service Deployment**
- FreeRouter as systemd service
- Web dashboard on port 8000
- API endpoint for script generation

**Task 3.2.3: Monitoring**
- Health check endpoints
- Usage logging
- Alert configuration

---

## Part 4: File Changes Summary

### New Files to Create

| File | Purpose |
|------|---------|
| `freerouter/providers_new.py` | New provider definitions |
| `packages/content_factory/topic_finder/trend_analyzer.py` | Trend analysis |
| `packages/content_factory/script_generator/jh_style.py` | JH style templates |
| `scripts/generate_video_script.py` | Standalone script generator |
| `tests/test_new_providers.py` | Provider tests |

### Files to Modify

| File | Changes |
|------|---------|
| `freerouter/providers.py` | Add new providers |
| `freerouter/router.py` | Enhance routing logic |
| `freerouter/.env.example` | Add new API key slots |
| `packages/content_factory/topic_finder/finder.py` | Integrate trends |

---

## Part 5: Key Questions for User

1. **API Keys:** Please provide the exact names of environment variables expected by each provider
2. **APIFreeLlm & z.ai:** Need documentation links or API endpoints for these providers
3. **Trend Sources:** Which trend sources should be prioritized? (Google Trends, YouTube, Twitter, Reddit)
4. **Output Format:** Preferred script output format? (Markdown, JSON, Google Docs, Notion)
5. **Duration:** Target video duration? (Short-form 3-5 min, Medium 8-12 min, Long-form 15+ min)

---

## Implementation Order

### Phase 1: Provider Infrastructure (Priority: HIGH)
1. Add Grok, Mistral, Sambanova, Cerebras, GitHub Models
2. Update .env.example with new keys
3. Test each provider individually
4. Test failover chain

### Phase 2: Script Generation Core (Priority: HIGH)
1. Create JH style templates
2. Implement dual-column generator
3. Add localization layer
4. Create standalone script

### Phase 3: Topic Enhancement (Priority: MEDIUM)
1. Add trend analyzer
2. Implement content gap analysis
3. Integrate with topic finder

### Phase 4: Testing & Deployment (Priority: HIGH)
1. Local testing
2. Oracle Cloud deployment
3. Monitoring setup

---

## Estimated Effort

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Phase 1 | Provider additions | 2-3 hours |
| Phase 2 | Script generation | 3-4 hours |
| Phase 3 | Topic enhancement | 2-3 hours |
| Phase 4 | Testing & deploy | 2-3 hours |
| **Total** | | **9-13 hours** |

---

*Document created for branch: Explaining-FinalRefactoring*
*Ready for user review and approval before implementation*
