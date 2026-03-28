# Implementation Plan V2: Self-Evolving Script Generation System

**Branch:** `Explaining-FinalRefactoring`
**Date:** 2025-03-25
**Status:** PLANNING PHASE - NOT IMPLEMENTING YET

---

## Executive Summary

This document outlines a comprehensive plan for:

1. **Multi-Provider FreeRouter System** - Automatic failover across free-tier AI providers
2. **Self-Evolving Script Generation** - Iterative loop based on Karpathy's auto-research methodology
3. **Trend-Based Topic Discovery** - Multi-source trend analysis
4. **Complexity-Adaptive Output** - Duration scales with topic complexity

---

# PART 1: SELF-EVOLVING SCRIPT GENERATION SYSTEM

## 1.1 Core Concept: Karpathy's Auto-Research Loop

The system implements Andrej Karpathy's iterative self-evaluation methodology where:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SELF-EVOLVING SCRIPT LOOP                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────┐                                                  │
│   │   START     │                                                  │
│   └──────┬──────┘                                                  │
│          │                                                          │
│          ▼                                                          │
│   ┌─────────────────────────────────────────┐                      │
│   │  PHASE 1: TOPIC DISCOVERY               │                      │
│   │  ─────────────────────────────────────  │                      │
│   │  Source Priority:                       │                      │
│   │  1. YouTube Trends (FIRST)              │                      │
│   │  2. Google Trends                       │                      │
│   │  3. Instagram Trends                    │                      │
│   │  4. Twitter/X Trends                    │                      │
│   │                                         │                      │
│   │  → Cross-reference with content gaps    │                      │
│   │  → Score topic viability (17 criteria)  │                      │
│   │  → Assess complexity level              │                      │
│   └──────────────────┬──────────────────────┘                      │
│                      │                                              │
│                      ▼                                              │
│   ┌─────────────────────────────────────────┐                      │
│   │  COMPLEXITY ASSESSMENT                   │                      │
│   │  ─────────────────────────────────────  │                      │
│   │                                         │                      │
│   │  Low Complexity    → SHORT (3-5 min)    │                      │
│   │  Medium Complexity  → MEDIUM (8-12 min) │                      │
│   │  High Complexity   → LONG (15+ min)     │                      │
│   │                                         │                      │
│   │  Factors:                               │                      │
│   │  - Number of hidden mechanisms          │                      │
│   │  - Visual asset availability            │                      │
│   │  - Audience prior knowledge gap         │                      │
│   │  - Emotional resonance potential        │                      │
│   └──────────────────┬──────────────────────┘                      │
│                      │                                              │
│                      ▼                                              │
│   ┌─────────────────────────────────────────┐                      │
│   │  PHASE 2: INITIAL RESEARCH              │                      │
│   │  ─────────────────────────────────────  │                      │
│   │  - Web search aggregation               │                      │
│   │  - Source credibility scoring           │                      │
│   │  - Fact extraction                      │                      │
│   │  - Visual asset identification          │                      │
│   └──────────────────┬──────────────────────┘                      │
│                      │                                              │
│          ┌───────────┴───────────┐                                  │
│          │                       │                                  │
│          ▼                       ▼                                  │
│   ┌────────────────┐    ┌────────────────┐                         │
│   │  User Approval │    │  Auto Mode     │                         │
│   │  (Manual Mode) │    │  (Bypass Gate) │                         │
│   └───────┬────────┘    └───────┬────────┘                         │
│           │                     │                                   │
│           └──────────┬──────────┘                                   │
│                      │                                              │
│                      ▼                                              │
│   ╔═════════════════════════════════════════╗                      │
│   ║     ITERATIVE SCRIPT REFINEMENT LOOP    ║                      │
│   ║     ─────────────────────────────────── ║                      │
│   ║                                         ║                      │
│   ║  ┌───────────────────────────────────┐  ║                      │
│   ║  │ ITERATION N                       │  ║                      │
│   ║  │                                   │  ║                      │
│   ║  │  1. Generate Script Draft         │  ║                      │
│   ║  │     - Use current prompt strategy │  ║                      │
│   ║  │     - Apply JH style patterns     │  ║                      │
│   ║  │     - Match target duration       │  ║                      │
│   ║  │                                   │  ║                      │
│   ║  │  2. Self-Evaluation               │  ║                      │
│   ║  │     - Compare against questions   │  ║                      │
│   ║  │     - Score each criterion        │  ║                      │
│   ║  │     - Identify weak points        │  ║                      │
│   ║  │                                   │  ║                      │
│   ║  │  3. Gap Analysis                  │  ║                      │
│   ║  │     - What's missing?             │  ║                      │
│   ║  │     - What's weak?                │  ║                      │
│   ║  │     - What contradicts research?  │  ║                      │
│   ║  │                                   │  ║                      │
│   ║  │  4. Prompt Strategy Adjustment    │  ║                      │
│   ║  │     - Modify emphasis areas       │  ║                      │
│   ║  │     - Add missing context         │  ║                      │
│   ║  │     - Refine structural guidance  │  ║                      │
│   ║  │                                   │  ║                      │
│   ║  │  5. Score Calculation             │  ║                      │
│   ║  │     - Production Readiness %      │  ║                      │
│   ║  │     - Convergence check           │  ║                      │
│   ║  │                                   │  ║                      │
│   ║  └───────────────┬───────────────────┘  ║                      │
│   ║                  │                       ║                      │
│   ║         ┌────────┴────────┐              ║                      │
│   ║         ▼                 ▼              ║                      │
│   ║   ┌───────────┐    ┌───────────┐        ║                      │
│   ║   │ Score ≥   │    │ Score <   │        ║                      │
│   ║   │ THRESHOLD │    │ THRESHOLD │        ║                      │
│   ║   │ (85%+)    │    │ (85%)     │        ║                      │
│   ║   └─────┬─────┘    └─────┬─────┘        ║                      │
│   ║         │                │               ║                      │
│   ║         │                ▼               ║                      │
│   ║         │         ┌──────────────┐      ║                      │
│   ║         │         │ Max Iterations│      ║                      │
│   ║         │         │ Reached?     │      ║                      │
│   ║         │         └──────┬───────┘      ║                      │
│   ║         │                │               ║                      │
│   ║         │        ┌───────┴───────┐       ║                      │
│   ║         │        ▼               ▼       ║                      │
│   ║         │   ┌─────────┐   ┌──────────┐  ║                      │
│   ║         │   │ YES     │   │ NO       │  ║                      │
│   ║         │   │(Exit    │   │(Continue │  ║                      │
│   ║         │   │ Loop)   │   │ Loop)    │  ║                      │
│   ║         │   └────┬────┘   └────┬─────┘  ║                      │
│   ║         │        │             │         ║                      │
│   ║         │        │      ┌──────┘         ║                      │
│   ║         │        │      │                ║                      │
│   ║         │        │      ▼                ║                      │
│   ║         │        │  ┌─────────────────┐  ║                      │
│   ║         │        │  │ N+1 Iteration   │  ║                      │
│   ║         │        │  │ (Refined Prompt)│  ║                      │
│   ║         │        │  └─────────────────┘  ║                      │
│   ║         │        │                       ║                      │
│   ║         └────────┴───────────────────────║                      │
│   ║                  │                       ║                      │
│   ╚══════════════════╪═══════════════════════╝                      │
│                      │                                              │
│                      ▼                                              │
│   ┌─────────────────────────────────────────┐                      │
│   │  PHASE 3: LOCALIZATION                   │                      │
│   │  ─────────────────────────────────────  │                      │
│   │  - Adapt for Pakistan audience          │                      │
│   │  - Local references & examples          │                      │
│   │  - Cultural resonance adjustment        │                      │
│   │  - Language considerations              │                      │
│   └──────────────────┬──────────────────────┘                      │
│                      │                                              │
│                      ▼                                              │
│   ┌─────────────────────────────────────────┐                      │
│   │  PHASE 4: FINAL OUTPUT                   │                      │
│   │  ─────────────────────────────────────  │                      │
│   │  - Deliver to Notion                    │                      │
│   │  - Dual-column format                   │                      │
│   │  - Production notes                     │                      │
│   │  - Visual asset list                    │                      │
│   └─────────────────────────────────────────┘                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 1.2 Self-Evaluation Questions (The Core Loop)

The system compares generated scripts against a set of evaluation questions:

### Hook Evaluation
| ID | Question | Weight |
|----|----------|--------|
| H1 | Does the hook create immediate curiosity? | 10% |
| H2 | Is the mainstream assumption clearly stated? | 8% |
| H3 | Does the visual anchor appear within 5 seconds? | 7% |

### Narrative Evaluation
| ID | Question | Weight |
|----|----------|--------|
| N1 | Does each section have a clear purpose? | 8% |
| N2 | Is the hidden mechanism explained visually? | 10% |
| N3 | Are transitions smooth between sections? | 6% |
| N4 | Is the pacing appropriate for complexity? | 7% |

### Evidence Evaluation
| ID | Question | Weight |
|----|----------|--------|
| E1 | Is every claim supported by research? | 10% |
| E2 | Are sources credible and current? | 8% |
| E3 | Is the smoking gun visually compelling? | 8% |

### Audience Connection
| ID | Question | Weight |
|----|----------|--------|
| A1 | Does this matter to Pakistani audience? | 8% |
| A2 | Is local context properly integrated? | 6% |
| A3 | Does it explain "why things are this way"? | 6% |

### Production Readiness
| ID | Question | Weight |
|----|----------|--------|
| P1 | Can every visual direction be executed? | 6% |
| P2 | Is the duration appropriate for topic? | 4% |
| P3 | Are archival assets accessible? | 6% |

**Total: 100% | Threshold: 85%**

## 1.3 Prompt Strategy Adjustment Logic

When score < 85%, the system adjusts prompts:

```python
class PromptStrategyAdjuster:
    """Adjusts prompts based on evaluation gaps."""
    
    def analyze_weak_areas(self, scores: dict) -> list[str]:
        """Identify which areas scored below threshold."""
        weak_areas = []
        for question_id, score in scores.items():
            if score < 0.7:  # Below 70% on this question
                weak_areas.append(question_id)
        return weak_areas
    
    def generate_adjusted_prompt(
        self, 
        original_prompt: str,
        weak_areas: list[str],
        iteration: int
    ) -> str:
        """Generate refined prompt with targeted improvements."""
        
        adjustments = {
            "H1": "Focus more on creating immediate curiosity in the hook. Use a provocative question or surprising statement.",
            "H2": "Make the mainstream assumption more explicit. State what people commonly believe before revealing the truth.",
            "N2": "Include more visual descriptions for the hidden mechanism. Use diagrams, animations, or B-roll suggestions.",
            "E1": "Add more source citations. Every factual claim should reference research.",
            # ... more adjustments for each question
        }
        
        strategy_hints = "\n".join([
            adjustments.get(area, "") 
            for area in weak_areas
        ])
        
        return f"""
{original_prompt}

=== ITERATION {iteration} REFINEMENT ===
Previous attempt scored low on: {', '.join(weak_areas)}

SPECIFIC IMPROVEMENTS NEEDED:
{strategy_hints}

Remember: Output must score 85%+ on all evaluation criteria.
"""
```

## 1.4 Convergence Detection

```python
class ConvergenceTracker:
    """Tracks if the loop is converging or stuck."""
    
    def __init__(self, max_iterations: int = 10, patience: int = 3):
        self.max_iterations = max_iterations
        self.patience = patience  # Stop if no improvement for N iterations
        self.score_history = []
    
    def check_convergence(self, current_score: float) -> tuple[bool, str]:
        """
        Returns (should_stop, reason).
        """
        self.score_history.append(current_score)
        
        # Check if threshold met
        if current_score >= 0.85:
            return True, "Threshold reached"
        
        # Check max iterations
        if len(self.score_history) >= self.max_iterations:
            return True, "Max iterations reached"
        
        # Check for stagnation
        if len(self.score_history) >= self.patience:
            recent = self.score_history[-self.patience:]
            if max(recent) - min(recent) < 0.02:  # Less than 2% variation
                return True, "Stagnation detected - no improvement"
        
        # Check for degradation
        if len(self.score_history) >= 2:
            if current_score < self.score_history[-2] - 0.05:
                # Score dropped significantly - might need different approach
                return False, "Score degraded - trying different strategy"
        
        return False, "Continue iterating"
```

---

# PART 2: TREND ANALYSIS SYSTEM

## 2.1 Trend Source Priority

```
┌─────────────────────────────────────────────────────────────┐
│                    TREND ANALYSIS PIPELINE                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Priority 1: YOUTUBE TRENDS                                │
│   ─────────────────────────────                             │
│   - Most relevant for video content                         │
│   - Shows what's already working                            │
│   - Reveals audience engagement patterns                    │
│   - API: YouTube Data API v3                                │
│                                                             │
│          │                                                  │
│          ▼                                                  │
│                                                             │
│   Priority 2: GOOGLE TRENDS                                 │
│   ─────────────────────────────                             │
│   - Broad interest indicators                               │
│   - Regional focus (Pakistan)                               │
│   - Related queries expansion                               │
│   - API: trends.google.com (scraping or API)               │
│                                                             │
│          │                                                  │
│          ▼                                                  │
│                                                             │
│   Priority 3: INSTAGRAM TRENDS                             │
│   ─────────────────────────────                             │
│   - Visual trend identification                             │
│   - Reels/short-form patterns                               │
│   - Hashtag analysis                                        │
│   - API: Meta Graph API (limited) or scraping              │
│                                                             │
│          │                                                  │
│          ▼                                                  │
│                                                             │
│   Priority 4: TWITTER/X TRENDS                             │
│   ─────────────────────────────                             │
│   - Real-time conversation topics                           │
│   - Hashtag momentum                                        │
│   - Influencer discussions                                  │
│   - API: X API v2 (requires access)                        │
│                                                             │
│          │                                                  │
│          ▼                                                  │
│                                                             │
│   CROSS-REFERENCE ENGINE                                    │
│   ─────────────────────────────                             │
│   - Find topics appearing in multiple sources              │
│   - Score based on source priority weights                  │
│   - Filter by content gap (not already covered)            │
│   - Assess alignment with channel niche                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 2.2 Trend Aggregation Logic

```python
class TrendAggregator:
    """Aggregates trends from multiple sources with priority weighting."""
    
    SOURCE_WEIGHTS = {
        "youtube": 0.40,    # 40% weight - most important
        "google": 0.30,     # 30% weight
        "instagram": 0.20,  # 20% weight
        "twitter": 0.10,    # 10% weight - least (rate limited)
    }
    
    async def aggregate_trends(
        self, 
        region: str = "PK",
        category: str = None,
        time_window: str = "7d"
    ) -> list[AggregatedTrend]:
        """
        Fetch trends from all sources and aggregate.
        """
        trends = []
        
        # 1. YouTube Trends (First Priority)
        yt_trends = await self.fetch_youtube_trends(region, category)
        for t in yt_trends:
            trends.append(AggregatedTrend(
                topic=t.title,
                source="youtube",
                engagement_score=t.view_count,
                momentum=self.calculate_momentum(t),
                weight=self.SOURCE_WEIGHTS["youtube"]
            ))
        
        # 2. Google Trends (Second Priority)
        gt_trends = await self.fetch_google_trends(region, time_window)
        for t in gt_trends:
            # Check if already exists from YouTube
            existing = self.find_matching_topic(trends, t.query)
            if existing:
                existing.add_source("google", self.SOURCE_WEIGHTS["google"])
            else:
                trends.append(AggregatedTrend(
                    topic=t.query,
                    source="google",
                    engagement_score=t.search_volume,
                    momentum=t.trend_change,
                    weight=self.SOURCE_WEIGHTS["google"]
                ))
        
        # 3. Instagram Trends (Third Priority)
        ig_trends = await self.fetch_instagram_trends(region)
        # Similar logic - add or merge
        
        # 4. Twitter/X Trends (Fourth Priority)
        x_trends = await self.fetch_twitter_trends(region)
        # Similar logic - add or merge
        
        # Calculate composite score
        for trend in trends:
            trend.composite_score = self.calculate_composite_score(trend)
        
        return sorted(trends, key=lambda x: x.composite_score, reverse=True)
```

---

# PART 3: COMPLEXITY-BASED DURATION SYSTEM

## 3.1 Complexity Assessment

```python
class ComplexityAssessor:
    """Assesses topic complexity to determine optimal video duration."""
    
    COMPLEXITY_FACTORS = {
        "hidden_mechanisms": {
            "weight": 0.25,
            "scoring": {
                "single_clear_mechanism": 1,
                "multiple_related_mechanisms": 2,
                "complex_interconnected_systems": 3
            }
        },
        "visual_asset_availability": {
            "weight": 0.20,
            "scoring": {
                "abundant_broll_archive": 1,
                "some_visuals_available": 2,
                "requires_custom_creation": 3
            }
        },
        "audience_knowledge_gap": {
            "weight": 0.25,
            "scoring": {
                "familiar_territory_new_angle": 1,
                "partially_known_concept": 2,
                "completely_new_territory": 3
            }
        },
        "emotional_depth": {
            "weight": 0.15,
            "scoring": {
                "informational_with_hooks": 1,
                "moderate_emotional_journey": 2,
                "deep_emotional_resonance": 3
            }
        },
        "source_complexity": {
            "weight": 0.15,
            "scoring": {
                "few_reliable_sources": 1,
                "multiple_source_synthesis": 2,
                "extensive_research_required": 3
            }
        }
    }
    
    DURATION_MAPPING = {
        "short": {  # 3-5 minutes
            "min_score": 1.0,
            "max_score": 1.6,
            "duration_seconds": (180, 300),
            "structure": "hook → reveal → conclusion"
        },
        "medium": {  # 8-12 minutes
            "min_score": 1.6,
            "max_score": 2.3,
            "duration_seconds": (480, 720),
            "structure": "hook → investigation → reveal → conclusion"
        },
        "long": {  # 15+ minutes
            "min_score": 2.3,
            "max_score": 3.0,
            "duration_seconds": (900, 1800),
            "structure": "hook → deep_investigation → multiple_reveals → conclusion"
        }
    }
    
    def assess_complexity(
        self, 
        topic: TopicBrief,
        research_data: dict
    ) -> ComplexityReport:
        """
        Assess topic complexity and recommend duration.
        """
        scores = {}
        
        # Score each factor
        for factor, config in self.COMPLEXITY_FACTORS.items():
            raw_score = self._evaluate_factor(factor, topic, research_data)
            scores[factor] = raw_score * config["weight"]
        
        # Calculate weighted average
        composite_score = sum(scores.values())
        
        # Map to duration
        for duration_type, mapping in self.DURATION_MAPPING.items():
            if mapping["min_score"] <= composite_score <= mapping["max_score"]:
                return ComplexityReport(
                    score=composite_score,
                    recommended_duration=duration_type,
                    duration_range=mapping["duration_seconds"],
                    structure_template=mapping["structure"],
                    factor_breakdown=scores
                )
        
        # Default to medium if unclear
        return ComplexityReport(
            score=composite_score,
            recommended_duration="medium",
            duration_range=(480, 720),
            structure_template="hook → investigation → reveal → conclusion",
            factor_breakdown=scores
        )
```

---

# PART 4: MULTI-PROVIDER FREEROUTER SYSTEM

## 4.1 Provider Configuration

### Existing Providers
| Provider | Priority | Type | Free Tier Limits |
|----------|----------|------|------------------|
| Ollama | 10 | Local | Unlimited |
| Groq | 20 | Cloud | 14,400 req/day |
| OpenRouter | 30 | Cloud | Model-dependent |
| Together | 40 | Cloud | Limited free |
| DeepInfra | 50 | Cloud | Pay-per-use |
| OpenAI | 60 | Cloud | No free tier |
| Anthropic | 70 | Cloud | No free tier |

### New Providers to Add

| Provider | Priority | Free Tier | API Endpoint | Auth Method |
|----------|----------|-----------|--------------|-------------|
| **Grok (X.AI)** | 25 | Limited | `api.x.ai/v1` | API Key |
| **Mistral** | 35 | Yes | `api.mistral.ai/v1` | API Key |
| **SambaNova** | 45 | Yes | `api.sambanova.ai/v1` | API Key |
| **Cerebras** | 55 | Yes | `api.cerebras.ai/v1` | API Key |
| **GitHub Models** | 65 | Yes | `models.inference.ai.azure.com` | GitHub Token |
| **APIFreeLLM** | 75 | Yes | TBD (research needed) | TBD |
| **z.ai** | 80 | Yes | TBD (research needed) | TBD |

## 4.2 Provider Implementation Template

```python
# File: freerouter/src/freerouter/providers.py

# Add to KNOWN_PROVIDERS list:

ProviderDefinition(
    name="grok",
    display_name="Grok (X.AI)",
    provider_type=ProviderType.CLOUD,
    env_key="GROK_API_KEY",
    base_url="https://api.x.ai/v1",
    health_url="https://api.x.ai/v1/models",
    signup_url="https://console.x.ai/",
    priority=25,
    daily_request_limit=100,  # Adjust based on actual limits
    rate_limit_reset_seconds=60,
),

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

ProviderDefinition(
    name="github",
    display_name="GitHub Models",
    provider_type=ProviderType.CLOUD,
    env_key="GITHUB_TOKEN",
    base_url="https://models.inference.ai.azure.com",
    health_url="https://models.inference.ai.azure.com/models",
    signup_url="https://github.com/settings/tokens",
    priority=65,
    requires_auth=True,
),

# DEFAULT_MODELS updates:
DEFAULT_MODELS.update({
    "grok": "grok-2-latest",
    "mistral": "mistral-small-latest",
    "sambanova": "Meta-Llama-3.1-8B-Instruct",
    "cerebras": "llama-3.3-70b",
    "github": "gpt-4o-mini",
})
```

## 4.3 Environment Configuration

```bash
# File: freerouter/.env

# =============================================================================
# FREE TIER API KEYS - Add your keys here
# =============================================================================

# --- Existing Providers ---
OPENROUTER_API_KEY=your_key_here
GROQ_API_KEY=your_key_here

# --- New Providers ---
# Grok (X.AI) - https://console.x.ai/
GROK_API_KEY=your_key_here

# Mistral AI - https://console.mistral.ai/
MISTRAL_API_KEY=your_key_here

# SambaNova - https://cloud.sambanova.ai/
SAMBANOVA_API_KEY=your_key_here

# Cerebras - https://cloud.cerebras.ai/
CEREBRAS_API_KEY=your_key_here

# GitHub Models - https://github.com/settings/tokens
# Requires 'models:read' scope
GITHUB_TOKEN=your_token_here

# --- Research Needed ---
# APIFreeLLM - https://apifreellm.com/en/api-access
APIFREELLM_API_KEY=your_key_here

# z.ai - documentation TBD
ZAI_API_KEY=your_key_here

# =============================================================================
# LOCAL PROVIDER (No key needed)
# =============================================================================
OLLAMA_BASE_URL=http://localhost:11434/v1
```

---

# PART 5: NOTION OUTPUT INTEGRATION

## 5.1 Notion Page Structure

```
📊 Video Script: [Topic Title]
├── 📋 Overview
│   ├── Topic Statement
│   ├── Big Question
│   ├── Target Duration
│   ├── Complexity Score
│   └── Production Readiness Score
│
├── 📈 Trend Sources
│   ├── YouTube Trend Score
│   ├── Google Trend Score
│   ├── Instagram Trend Score
│   └── Twitter Trend Score
│
├── 📝 Dual-Column Script
│   ├── Section 1: HOOK (0:00-0:30)
│   │   ├── Narration: "..."
│   │   └── Visual: [B-roll description]
│   ├── Section 2: ANCHOR (0:30-1:00)
│   ├── Section 3: BRIDGE (1:00-2:00)
│   ├── Section 4: REVEAL (2:00-3:00)
│   └── Section 5: CONCLUSION
│
├── 🔍 Research Sources
│   ├── Source 1: [URL] - Credibility Score
│   ├── Source 2: [URL] - Credibility Score
│   └── ...
│
├── 🎬 Visual Assets Needed
│   ├── Archive footage: [List]
│   ├── Maps/Graphics: [List]
│   ├── B-roll: [List]
│   └── Custom animations: [List]
│
├── 📊 Self-Evaluation Log
│   ├── Iteration 1: Score 72% - Weak: H1, N2
│   ├── Iteration 2: Score 78% - Weak: E1
│   ├── Iteration 3: Score 85% ✓ APPROVED
│   └── ...
│
└── ✅ Production Checklist
    ├── Script approved
    ├── Research verified
    ├── Visuals sourced
    └── Ready for production
```

## 5.2 Notion Integration Code

```python
# File: packages/integrations/notion/script_publisher.py

from notion_client import Client

class ScriptPublisher:
    """Publishes completed scripts to Notion."""
    
    def __init__(self, notion_token: str, database_id: str):
        self.client = Client(auth=notion_token)
        self.database_id = database_id
    
    async def publish_script(
        self,
        script: DualColumnScript,
        complexity_report: ComplexityReport,
        trend_data: AggregatedTrend,
        evaluation_log: list[dict]
    ) -> str:
        """
        Create a Notion page with the complete script.
        Returns the page URL.
        """
        
        # Create main page
        page = self.client.pages.create(
            parent={"database_id": self.database_id},
            properties={
                "Title": {"title": [{"text": {"content": script.adapted_title}}]},
                "Status": {"select": {"name": "Ready for Review"}},
                "Duration": {"select": {"name": complexity_report.recommended_duration}},
                "Complexity Score": {"number": complexity_report.score},
                "Production Readiness": {"number": script.production_readiness_score},
            }
        )
        
        # Add content blocks
        blocks = self._build_content_blocks(
            script, complexity_report, trend_data, evaluation_log
        )
        
        self.client.blocks.children.append(
            block_id=page["id"],
            children=blocks
        )
        
        return page["url"]
```

---

# PART 6: FILE STRUCTURE

## 6.1 New Files to Create

```
AI-Orchestration/
├── packages/
│   ├── content_factory/
│   │   ├── script_generator/
│   │   │   ├── __init__.py
│   │   │   ├── jh_style.py           # Johnny Harris style templates
│   │   │   ├── dual_column.py        # Dual-column script generator
│   │   │   └── prompt_adjuster.py    # Prompt strategy adjustment
│   │   │
│   │   ├── evaluation/
│   │   │   ├── __init__.py
│   │   │   ├── self_evaluator.py     # Self-evaluation engine
│   │   │   ├── convergence.py        # Convergence tracking
│   │   │   └── questions.py          # Evaluation questions
│   │   │
│   │   ├── trend_analysis/
│   │   │   ├── __init__.py
│   │   │   ├── aggregator.py         # Multi-source trend aggregation
│   │   │   ├── youtube_trends.py     # YouTube trend fetcher
│   │   │   ├── google_trends.py      # Google Trends fetcher
│   │   │   ├── instagram_trends.py   # Instagram trend fetcher
│   │   │   └── twitter_trends.py     # Twitter/X trend fetcher
│   │   │
│   │   └── complexity/
│   │       ├── __init__.py
│   │       └── assessor.py           # Complexity assessment
│   │
│   └── integrations/
│       └── notion/
│           └── script_publisher.py   # Notion output
│
├── scripts/
│   └── generate_video_script.py      # Main entry point
│
└── freerouter/
    └── src/freerouter/
        └── providers.py              # Add new providers
```

## 6.2 Files to Modify

| File | Changes |
|------|---------|
| `freerouter/providers.py` | Add 7 new providers |
| `freerouter/router.py` | Enhanced routing for script tasks |
| `packages/content_factory/topic_finder/finder.py` | Integrate trend analysis |
| `packages/content_factory/adaptation/stage4_script.py` | Connect to new generator |
| `scripts/auto_production.py` | Use new self-evolving loop |

---

# PART 7: IMPLEMENTATION PHASES

## Phase 1: Provider Infrastructure (Days 1-2)
- [ ] Add Grok, Mistral, Sambanova, Cerebras, GitHub Models
- [ ] Update .env.example with new key slots
- [ ] Test each provider individually
- [ ] Test failover chain
- [ ] Research APIFreeLLM and z.ai endpoints

## Phase 2: Self-Evaluation Engine (Days 3-4)
- [ ] Create evaluation questions database
- [ ] Implement self-evaluator
- [ ] Build convergence tracker
- [ ] Create prompt adjustment logic
- [ ] Test iterative loop with mock data

## Phase 3: Trend Analysis (Days 5-6)
- [ ] YouTube trends fetcher
- [ ] Google Trends integration
- [ ] Instagram trends fetcher
- [ ] Twitter/X trends fetcher
- [ ] Cross-reference aggregation

## Phase 4: Complexity Assessment (Day 7)
- [ ] Implement complexity factors
- [ ] Duration mapping logic
- [ ] Integration with script generator

## Phase 5: Integration & Testing (Days 8-9)
- [ ] Connect all components
- [ ] End-to-end testing
- [ ] Notion output integration
- [ ] Performance optimization

## Phase 6: Deployment (Day 10)
- [ ] Local testing
- [ ] Oracle Cloud deployment
- [ ] Monitoring setup

---

# PART 8: QUESTIONS FOR USER

## Critical Information Needed:

1. **APIFreeLLM API Documentation**
   - What is the API endpoint?
   - What authentication method?
   - What models are available?
   - What are the rate limits?

2. **z.ai API Documentation**
   - Same questions as above

3. **Notion Integration**
   - Do you have a Notion integration token?
   - What database ID should scripts be added to?

4. **YouTube API**
   - Do you have a YouTube Data API key?

5. **Twitter/X API**
   - Do you have X API access? (requires paid tier for trends)

6. **Instagram API**
   - Do you have Meta Developer access for Instagram?

7. **Threshold Preferences**
   - Is 85% production readiness threshold acceptable?
   - Maximum iterations for the loop (10 default)?

---

*Plan Version: 2.0*
*Status: Awaiting User Approval and Information*
*Ready to implement once all questions are answered*
