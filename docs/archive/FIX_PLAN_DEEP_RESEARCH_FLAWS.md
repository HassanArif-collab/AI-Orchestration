# Fix Plan: Deep Research System Flaws

**Date**: 2026-03-25
**Status**: Planning Phase
**Branch**: `fix/deep-research-flaws` (to be created)

---

## Overview

This document outlines the plan to fix 9 identified flaws in the Deep Research integration system. Fixes are prioritized by impact and grouped into logical implementation phases.

---

## Phase 1: Critical Fixes (P0)

### 1.1 Fix: Cache Hit Not Actually Used

**File**: `packages/pipeline/handlers.py`
**Lines**: 126-131

**Current Problem**:
```python
if cached_research:
    logger.info(f"research_cache_hit: topic='...'" )
    # TODO: Consider caching AdaptedScript results instead
    # Code continues to do full research anyway!
```

**Solution**: Actually return the cached research instead of continuing.

**Implementation**:
```python
async def handle_research(run: PipelineRun, context: dict = None) -> dict:
    # ... existing code ...

    if use_cache:
        cache = ResearchCache(ttl_hours=cache_ttl_hours)
        cached_research = cache.get(brief.topic_statement)

        if cached_research:
            logger.info(f"research_cache_hit: topic='{brief.topic_statement[:50]}...'")
            # Convert cached dossier back to ResearchDossier if needed
            if cached_research.get("format") == "legacy":
                # Legacy string format - use as-is
                return _build_script_from_research(cached_research.get("markdown", ""), brief)
            else:
                # ResearchDossier format - convert to AdaptedScript
                return _build_script_from_dossier(cached_research, brief)

    # Continue with normal research if no cache hit...
```

**New Helper Functions Needed**:
- `_build_script_from_research(research_markdown: str, brief: TopicBrief) -> dict`
- `_build_script_from_dossier(dossier_dict: dict, brief: TopicBrief) -> dict`

**Testing**: Unit test that verifies cache hit returns early without LLM calls.

---

### 1.2 Fix: Web Search Fallback Generates Fake URLs

**File**: `packages/router/web_search.py`
**Lines**: 131-188

**Current Problem**:
```python
async def _fallback_search(self, query: str, ...):
    """Fallback search using LLM to generate likely useful URLs."""
    # Asks LLM to hallucinate search results - DANGEROUS
```

**Solution**: Replace hallucination with real alternatives.

**Implementation Options** (choose one):

**Option A: Return Empty Results with Warning**
```python
async def _fallback_search(self, query: str, num_results: int = 10) -> list[SearchResult]:
    """Fallback when web search is unavailable - returns empty with clear indicator."""
    log.warning(f"web_search_unavailable_no_fallback: query='{query[:50]}'")
    # Return empty list - let upstream handle lack of data
    return []
```

**Option B: Use Alternative Search Provider**
```python
async def _fallback_search(self, query: str, num_results: int = 10) -> list[SearchResult]:
    """Try alternative search providers."""
    # Try DuckDuckGo HTML scraping (no API key needed)
    try:
        return await self._duckduckgo_search(query, num_results)
    except Exception as e:
        log.warning(f"all_search_providers_failed: {e}")
        return []
```

**Recommended**: Option A for safety, Option B if duckduckgo-search library is available.

**Testing**: Unit test that fallback never returns fabricated URLs.

---

### 1.3 Fix: No Throttling for Parallel Searches

**File**: `packages/router/web_search.py`
**Lines**: 190-218

**Current Problem**:
```python
async def multi_search(self, queries: list[str], ...):
    tasks = [self.search(q, num_per_query) for q in queries]
    results_lists = await asyncio.gather(*tasks)  # All fire at once!
```

**Solution**: Add rate limiting with configurable delays.

**Implementation**:
```python
class WebSearchClient:
    def __init__(
        self,
        rate_limit_per_second: float = 2.0,  # Max 2 searches per second
    ) -> None:
        self._zai = None
        self._rate_limiter = asyncio.Semaphore(int(rate_limit_per_second))
        self._last_search_time = 0.0
        self._min_interval = 1.0 / rate_limit_per_second

    async def _acquire_rate_limit(self) -> None:
        """Wait until rate limit allows next search."""
        async with self._rate_limiter:
            now = time.time()
            elapsed = now - self._last_search_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_search_time = time.time()

    async def multi_search(
        self,
        queries: list[str],
        num_per_query: int = 5,
        delay_between: float = 0.5,  # New parameter
    ) -> dict[str, list[SearchResult]]:
        """Perform multiple searches with throttling."""
        output = {}

        for i, query in enumerate(queries):
            if i > 0:
                await asyncio.sleep(delay_between)

            try:
                await self._acquire_rate_limit()
                results = await self.search(query, num_per_query)
                output[query] = results
            except Exception as e:
                log.warning(f"multi_search_query_failed: {query} -> {e}")
                output[query] = []

        return output
```

**Testing**: Unit test verifying rate limiting is respected.

---

## Phase 2: Data Quality Fixes (P1)

### 2.1 Fix: Facts Not Deduplicated

**File**: `packages/content_factory/production/deep_research.py`
**Lines**: 526-543

**Current Problem**:
```python
def _add_fact_to_dossier(self, dossier: ResearchDossier, fact: ResearchFact):
    # Just appends - no deduplication!
    dossier.facts_and_data.append(fact)
```

**Solution**: Add deduplication based on statement similarity.

**Implementation**:
```python
class ResearchDossier(BaseModel):
    # ... existing fields ...

    # Add a set to track seen statements
    _seen_statements: set[str] = PrivateAttr(default_factory=set)

    def _normalize_statement(self, statement: str) -> str:
        """Normalize statement for comparison."""
        # Remove extra whitespace, lowercase, strip punctuation
        normalized = re.sub(r'\s+', ' ', statement.lower().strip())
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return normalized[:100]  # Compare first 100 chars

    def _is_duplicate_fact(self, fact: ResearchFact) -> bool:
        """Check if fact is duplicate of existing one."""
        normalized = self._normalize_statement(fact.statement)
        if normalized in self._seen_statements:
            return True

        # Check for similar statements (not exact match)
        for seen in self._seen_statements:
            # Simple similarity: overlap ratio
            overlap = len(set(normalized.split()) & set(seen.split()))
            total = len(set(normalized.split()) | set(seen.split()))
            if total > 0 and overlap / total > 0.8:  # 80% similarity threshold
                return True

        return False

    def add_fact_if_unique(self, fact: ResearchFact) -> bool:
        """Add fact only if not duplicate. Returns True if added."""
        if self._is_duplicate_fact(fact):
            log.debug(f"fact_deduplicated: {fact.statement[:50]}...")
            return False

        self._seen_statements.add(self._normalize_statement(fact.statement))
        self._add_fact_to_dossier(fact)
        return True
```

**Update DeepResearchEngine**:
```python
# In _phase_deep_dive and _phase_diversity_validation:
for fact in facts:
    dossier.add_fact_if_unique(fact)  # Changed from _add_fact_to_dossier
```

**Testing**: Unit test with duplicate facts verifying only one is kept.

---

## Phase 3: Resilience Fixes (P2)

### 3.1 Fix: No Partial Results on Failure

**File**: `packages/content_factory/production/deep_research.py`
**Lines**: 141-186

**Current Problem**:
```python
async def research(self, topic: str, ...) -> ResearchDossier:
    for iteration in range(max_iterations):
        # Phase 1, 2, 3, 4...
        # If crash occurs, all progress is LOST
```

**Solution**: Add checkpoint mechanism with intermediate saves.

**Implementation**:
```python
class DeepResearchEngine:
    def __init__(
        self,
        router_client: Optional[RouterClient] = None,
        checkpoint_dir: Optional[Path] = None,
        ...
    ) -> None:
        # ... existing init ...
        self._checkpoint_dir = checkpoint_dir or Path(settings.DATA_DIR) / "research_checkpoints"
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _save_checkpoint(self, dossier: ResearchDossier, phase: str, iteration: int) -> None:
        """Save intermediate research state."""
        checkpoint = {
            "phase": phase,
            "iteration": iteration,
            "dossier": dossier.model_dump(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        checkpoint_file = self._checkpoint_dir / f"{self._topic_hash(dossier.topic)}.checkpoint.json"
        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint, f, indent=2, default=str)
        log.debug(f"checkpoint_saved: phase={phase} iteration={iteration}")

    def _load_checkpoint(self, topic: str) -> Optional[tuple[ResearchDossier, str, int]]:
        """Load previous checkpoint if exists."""
        checkpoint_file = self._checkpoint_dir / f"{self._topic_hash(topic)}.checkpoint.json"
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file) as f:
                    data = json.load(f)
                dossier = ResearchDossier(**data["dossier"])
                return dossier, data["phase"], data["iteration"]
            except Exception as e:
                log.warning(f"checkpoint_load_failed: {e}")
        return None

    async def research(self, topic: str, ...) -> ResearchDossier:
        # Try to resume from checkpoint
        checkpoint = self._load_checkpoint(topic)
        if checkpoint:
            dossier, last_phase, last_iteration = checkpoint
            log.info(f"resuming_from_checkpoint: phase={last_phase} iteration={last_iteration}")
        else:
            dossier = ResearchDossier(topic=topic, genre_id=genre)

        try:
            for iteration in range(max_iterations):
                # Phase 1
                if iteration == 0 and (not checkpoint or last_phase != "phase_1_complete"):
                    dimensions = await self._phase_broad_exploration(topic, dossier)
                    dossier.dimensions_explored = dimensions
                    self._save_checkpoint(dossier, "phase_1_complete", iteration)

                # Phase 2
                for dim in dimensions:
                    if self._search_count >= self.max_total_searches:
                        break
                    await self._phase_deep_dive(topic, dim, dossier)
                    self._save_checkpoint(dossier, f"phase_2_{dim}", iteration)

                # Phase 3
                await self._phase_diversity_validation(topic, dossier)
                self._save_checkpoint(dossier, "phase_3_complete", iteration)

                # Phase 4 - Check completion
                if dossier.is_complete(target_completeness):
                    break

            return dossier

        except Exception as e:
            # Save partial results on failure
            self._save_checkpoint(dossier, "failed", iteration)
            log.error(f"research_failed_checkpoint_saved: {e}")
            raise
```

**Testing**: Integration test that simulates crash and verifies recovery.

---

### 3.2 Fix: No Cross-Source Fact Validation

**File**: `packages/content_factory/production/deep_research.py`
**Lines**: 384-436

**Current Problem**: Facts are extracted but never validated against other sources.

**Solution**: Add fact validation with source corroboration.

**Implementation**:
```python
class ResearchFact(BaseModel):
    # ... existing fields ...
    corroboration_count: int = Field(
        default=1,
        description="Number of independent sources confirming this fact"
    )
    corroboration_sources: list[str] = Field(
        default_factory=list,
        description="URLs of sources that confirm this fact"
    )
    validation_status: str = Field(
        default="unverified",
        description="unverified, partially_verified, verified, disputed"
    )


class DeepResearchEngine:
    async def _validate_facts(self, dossier: ResearchDossier) -> None:
        """Cross-validate facts across multiple sources."""
        log.info("validating_facts_across_sources")

        # Group facts by topic/key claim
        all_facts = (
            dossier.facts_and_data +
            dossier.examples_cases +
            dossier.expert_opinions
        )

        for fact in all_facts:
            # Search for corroboration
            if fact.statement and len(fact.statement) > 20:
                # Extract key claim from statement
                key_claim = self._extract_key_claim(fact.statement)

                try:
                    results = await self._search(f'"{key_claim}" verification', num_results=3)

                    for r in results:
                        if r.url != fact.source_url:
                            # Check if result supports the fact
                            if self._statements_agree(fact.statement, r.snippet):
                                fact.corroboration_count += 1
                                fact.corroboration_sources.append(r.url)

                    # Update validation status
                    if fact.corroboration_count >= 2:
                        fact.validation_status = "verified"
                    elif fact.corroboration_count >= 1:
                        fact.validation_status = "partially_verified"

                except Exception as e:
                    log.debug(f"fact_validation_failed: {e}")

        log.info(f"fact_validation_complete: verified={sum(1 for f in all_facts if f.validation_status == 'verified')}")

    def _extract_key_claim(self, statement: str) -> str:
        """Extract the key claim from a statement for verification search."""
        # Simple approach: take first sentence, remove numbers and dates
        first_sentence = statement.split('.')[0]
        # Remove numbers (dates, statistics)
        key_claim = re.sub(r'\d+[%\s]*(million|billion|thousand)?', '', first_sentence, flags=re.I)
        return key_claim.strip()[:100]

    def _statements_agree(self, statement1: str, statement2: str) -> bool:
        """Check if two statements support the same claim."""
        # Simple heuristic: check for overlapping named entities and key terms
        words1 = set(re.findall(r'\b[A-Z][a-z]+\b', statement1))  # Named entities
        words2 = set(re.findall(r'\b[A-Z][a-z]+\b', statement2))

        if words1 and words2:
            overlap = len(words1 & words2)
            if overlap >= 1:  # At least one common named entity
                return True

        return False
```

**Testing**: Unit test with known facts and verification sources.

---

### 3.3 Fix: Experiment Loop Doesn't Persist Best Script

**File**: `packages/content_factory/evaluation/loop.py`
**Lines**: 33-121

**Current Problem**: Best script is only in memory - crash loses all progress.

**Solution**: Persist best script to disk after each iteration.

**Implementation**:
```python
class ExperimentLoop:
    def __init__(self, persist_dir: Optional[Path] = None) -> None:
        self.baseline = BaselineManager()
        self.scoring = ScoringEngine()
        self.challenger = ChallengerGenerator()
        self.logger = LearningLogger()
        self._persist_dir = persist_dir or Path(settings.DATA_DIR) / "experiment_snapshots"
        self._persist_dir.mkdir(parents=True, exist_ok=True)

    def _persist_best_script(self, script: AdaptedScript, cycle_id: str, iteration: int) -> None:
        """Save best script to disk."""
        snapshot = {
            "cycle_id": cycle_id,
            "iteration": iteration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "score": script.production_readiness_score,
            "script": script.model_dump(),
        }
        snapshot_file = self._persist_dir / f"{cycle_id}_best.json"
        temp_file = snapshot_file.with_suffix(".tmp")

        with open(temp_file, "w") as f:
            json.dump(snapshot, f, indent=2, default=str)

        temp_file.rename(snapshot_file)
        logger.debug(f"persisted_best_script: cycle={cycle_id} score={script.production_readiness_score:.1f}%")

    def _load_persisted_best(self, cycle_id: str) -> Optional[tuple[AdaptedScript, int]]:
        """Load previously persisted best script."""
        snapshot_file = self._persist_dir / f"{cycle_id}_best.json"
        if snapshot_file.exists():
            try:
                with open(snapshot_file) as f:
                    data = json.load(f)
                script = AdaptedScript(**data["script"])
                return script, data["iteration"]
            except Exception as e:
                logger.warning(f"persisted_script_load_failed: {e}")
        return None

    async def run_iterations(
        self,
        script: AdaptedScript,
        iterations: int = 3,
        router_client: RouterClient | None = None
    ) -> AdaptedScript:
        cycle_id = f"exp_{uuid.uuid4().hex[:8]}"

        # Check for persisted state (resume capability)
        persisted = self._load_persisted_best(cycle_id)
        if persisted:
            current_best, start_iteration = persisted
            logger.info(f"resuming_from_persisted: iteration={start_iteration}")
        else:
            current_best = script
            start_iteration = 0

        # ... existing loop logic ...

        for i in range(start_iteration, iterations):
            # ... iteration logic ...

            # Persist best after each iteration
            self._persist_best_script(current_best, cycle_id, i)

        return current_best
```

**Testing**: Integration test simulating crash during loop, verifying recovery.

---

## Phase 4: Optimization Fixes (P3)

### 4.1 Fix: No TTL Refresh for Frequently-Accessed Topics

**File**: `packages/pipeline/research_cache.py`
**Lines**: 81-124

**Current Problem**: Cache entries expire after fixed TTL regardless of access frequency.

**Solution**: Implement TTL refresh on access (LRU-like behavior).

**Implementation**:
```python
class ResearchCache:
    def __init__(
        self,
        ttl_hours: int = 24,
        cache_dir: Optional[Path] = None,
        refresh_ttl_on_access: bool = True,  # New parameter
        max_refreshes: int = 10,  # Max TTL refreshes before forced expiry
    ) -> None:
        # ... existing init ...
        self._refresh_ttl_on_access = refresh_ttl_on_access
        self._max_refreshes = max_refreshes

    def get(self, topic: str) -> Optional[dict]:
        """Retrieve cached research with optional TTL refresh."""
        cache_file = self._cache_path(topic)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            cached_at_str = data.get("_cached_at")
            refresh_count = data.get("_refresh_count", 0)

            if cached_at_str:
                cached_at = datetime.fromisoformat(cached_at_str)
                age = datetime.now(timezone.utc) - cached_at

                # Check if expired AND max refreshes not reached
                if age > self.ttl:
                    if self._refresh_ttl_on_access and refresh_count < self._max_refreshes:
                        # Refresh TTL
                        data["_cached_at"] = datetime.now(timezone.utc).isoformat()
                        data["_refresh_count"] = refresh_count + 1
                        data["_last_accessed"] = datetime.now(timezone.utc).isoformat()

                        # Re-save with refreshed TTL
                        with open(cache_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)

                        log.info(
                            f"cache_ttl_refreshed: topic='{topic[:50]}...' "
                            f"refresh_count={refresh_count + 1}/{self._max_refreshes}"
                        )
                    else:
                        # Max refreshes reached or refresh disabled - expire
                        log.info(
                            f"cache_expired_max_refreshes: topic='{topic[:50]}...' "
                            f"refresh_count={refresh_count}"
                        )
                        cache_file.unlink(missing_ok=True)
                        return None

            return data.get("dossier")

        except Exception as e:
            log.warning(f"cache_read_failed: {e}")
            return None

    def set(self, topic: str, dossier: dict) -> None:
        """Cache research results with access tracking."""
        cache_file = self._cache_path(topic)

        try:
            data = {
                "topic": topic,
                "dossier": dossier,
                "_cached_at": datetime.now(timezone.utc).isoformat(),
                "_refresh_count": 0,  # Initialize refresh counter
                "_last_accessed": datetime.now(timezone.utc).isoformat(),
                "_access_count": 1,
            }
            # ... rest of existing set logic ...
```

**Testing**: Unit test verifying TTL refresh on access and max refresh limit.

---

## Implementation Order

```
Phase 1 (Critical - Day 1)
├── 1.1 Cache Hit Not Used
├── 1.2 Web Search Fallback
└── 1.3 Rate Limiting

Phase 2 (Data Quality - Day 2)
└── 2.1 Facts Deduplication

Phase 3 (Resilience - Day 3-4)
├── 3.1 Partial Results Checkpoint
├── 3.2 Cross-Source Validation
└── 3.3 Experiment Loop Persistence

Phase 4 (Optimization - Day 5)
└── 4.1 TTL Refresh
```

---

## Testing Strategy

Each fix requires:

1. **Unit Test**: Test the specific fix in isolation
2. **Integration Test**: Test with the full research pipeline
3. **Regression Test**: Ensure existing functionality not broken

**Test Files to Create/Update**:
- `tests/test_research_cache.py` - Cache fixes
- `tests/test_web_search.py` - Rate limiting, fallback
- `tests/test_deep_research.py` - Deduplication, validation, checkpoints
- `tests/test_experiment_loop.py` - Persistence

---

## Risk Assessment

| Fix | Risk | Mitigation |
|-----|------|------------|
| Cache hit return | Breaking existing flow | Add feature flag `RESEARCH_CACHE_ENABLED` |
| Remove fake URLs | Research may fail more often | Log warnings clearly, allow retry |
| Rate limiting | Slower searches | Make configurable via env var |
| Fact validation | More API calls | Add feature flag, make optional |
| Checkpoints | Disk usage | Add cleanup of old checkpoints |

---

## Rollback Plan

Each phase will be on a separate branch:
1. `fix/cache-hit-usage`
2. `fix/web-search-fallback`
3. `fix/rate-limiting`
4. `fix/fact-deduplication`
5. `fix/research-checkpoints`
6. `fix/fact-validation`
7. `fix/experiment-persistence`
8. `fix/ttl-refresh`

All branches merge to `fix/deep-research-flaws` first, then to `main` after QA.

---

## Next Steps

1. **User Approval**: Review this plan and approve/deny specific fixes
2. **Create Branch**: `git checkout -b fix/deep-research-flaws`
3. **Implement Phase 1**: Start with critical fixes
4. **Test & Review**: Run test suite after each fix
5. **Merge**: After all phases complete and tested
