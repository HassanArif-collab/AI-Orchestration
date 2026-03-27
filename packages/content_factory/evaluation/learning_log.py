"""Phase 4 Auto-Research Loop: Learning Log.

Records the outcome of every ExperimentLoop mutation attempt.
This log is the RAW DATA that the SynthesisEngine processes weekly.

FORMAT (JSON Lines — one JSON object per line):
  {
    "cycle_id": "exp_abc123",      — ExperimentLoop run ID
    "genre_id": "islamic_history", — genre being mutated
    "baseline_id": "vid_abc",      — baseline script video_id
    "challenger_id": "mutated_xyz",— challenger script video_id
    "mutation_zone": "script_prose",— which zone was mutated
    "baseline_score": 72.5,        — score BEFORE mutation
    "challenger_score": 78.3,      — score AFTER mutation
    "beat_baseline": true,         — did challenger win?
    "fixed_questions": ["C3","C5"],— which questions improved
    "regressed_questions": ["B2"], — which questions got worse
  }

WHERE IT'S READ:
  1. SynthesisEngine — reads via Zep semantic search (when ZEP_ENABLED)
  2. ZepAudienceModelStore — migrates entries to Zep at init
  3. HealthMonitor — reads for dashboard learning system status

FILE LOCATION:
  packages/data/learning_log.jsonl (gitignored — runtime data)

MUTATION ZONES (three per script):
  script_prose         → questions C (prose quality) + F (conclusion)
  visual_direction     → questions B (visual anchors) + E (coding quality)
  structural_architecture → question D (anchor-bridge structure)
  Zone 3 only mutated AFTER Zone 1 and Zone 2 have been tried.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel

from packages.core.logger import get_logger
from packages.memory.client import AsyncZepMemoryClient
from packages.core.config import get_settings

logger = get_logger(__name__)

DEFAULT_LOG_PATH = "packages/data/learning_log.jsonl"


class LearningLogEntry(BaseModel):
    """A record of one mutation cycle.
    
    This is the ATOMIC UNIT of learning data. Each entry captures
    exactly one mutation attempt and its outcome.
    
    FIELDS:
      cycle_id: UUID of the experiment loop run
      genre_id: Video genre being tested
      baseline_id: ID of the script being challenged
      challenger_id: ID of the mutated script
      mutation_zone: Which of the 3 zones was mutated
      baseline_score: Score before mutation
      challenger_score: Score after mutation
      beat_baseline: Whether challenger won
      fixed_questions: Binary question IDs that improved
      regressed_questions: Binary question IDs that got worse
      timestamp: When this experiment happened
    """
    cycle_id: str
    genre_id: str
    baseline_id: str
    challenger_id: str
    mutation_zone: str
    baseline_score: float
    challenger_score: float
    beat_baseline: bool
    fixed_questions: list[str] = []
    regressed_questions: list[str] = []
    timestamp: datetime


class LearningLogger:
    """JSONL logger for tracking Auto-Research Loop experiments.
    
    Provides DUAL-WRITE: logs to local JSONL file AND to Zep Cloud.
    This ensures data survives restarts and is available for semantic
    search by the SynthesisEngine.
    
    LOCAL FILE:
      packages/data/learning_log.jsonl
      One JSON object per line (JSONL format)
    
    ZEP CLOUD:
      Session: {ZEP_LEARNING_USER_ID}_session
      Facts: One fact per experiment entry
    
    USAGE:
      logger = LearningLogger()
      
      # After each mutation cycle
      entry = LearningLogEntry(
          cycle_id="exp_123",
          genre_id="islamic_history",
          baseline_id="vid_abc",
          challenger_id="mutated_xyz",
          mutation_zone="script_prose",
          baseline_score=72.5,
          challenger_score=78.3,
          beat_baseline=True,
          fixed_questions=["C3", "C5"],
          timestamp=datetime.now(timezone.utc)
      )
      logger.log_experiment(entry)
    """

    def __init__(self, log_path: str = DEFAULT_LOG_PATH) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.zep_client = AsyncZepMemoryClient()
        self.learning_user_id = get_settings().ZEP_LEARNING_USER_ID
        self.zep_session_id = f"{self.learning_user_id}_session"

    def log_experiment(self, entry: LearningLogEntry) -> None:
        """Append an experiment record to the log.
        
        Writes to BOTH:
          1. Local JSONL file (always succeeds)
          2. Zep Cloud (graceful degradation if unavailable)
        
        Args:
            entry: The LearningLogEntry to record
        """
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
            
        # Zep dual-write (async, run in background)
        content = (f"Experiment in cycle {entry.cycle_id} for genre {entry.genre_id}. "
                   f"Zone '{entry.mutation_zone}' mutation resulted in score "
                   f"{entry.baseline_score}% -> {entry.challenger_score}%. "
                   f"Beat baseline: {entry.beat_baseline}.")
        if entry.fixed_questions:
            content += f" Fixed questions: {', '.join(entry.fixed_questions)}."
        if entry.regressed_questions:
            content += f" Regressed questions: {', '.join(entry.regressed_questions)}."
        
        metadata = {
            "log_type": "Successful Mutation" if entry.beat_baseline else "Failed Pattern",
            "production_cycle_id": entry.cycle_id,
            "genre": entry.genre_id,
            "zone_mutated": entry.mutation_zone,
            "score_before": entry.baseline_score,
            "score_after": entry.challenger_score,
            "promotion_decision": "Promoted" if entry.beat_baseline else "Discarded"
        }
        
        # Run async Zep write in background
        asyncio.create_task(self._write_to_zep(content, metadata))

        if entry.beat_baseline:
            logger.info(f"experiment_success: Zone {entry.mutation_zone} improved score from {entry.baseline_score:.1f}% to {entry.challenger_score:.1f}%")
        else:
            logger.info(f"experiment_failure: Zone {entry.mutation_zone} failed to beat {entry.baseline_score:.1f}%")

    async def _write_to_zep(self, content: str, metadata: dict) -> None:
        """Write a fact to Zep (async helper for background execution)."""
        try:
            await self.zep_client.add_facts(session_id=self.zep_session_id, facts=[{"fact": content, **metadata}])
        except Exception as e:
            logger.debug(f"zep_write_failed: {e}")

    def read_logs(self) -> list[LearningLogEntry]:
        """Read all experiment logs from local file.
        
        Useful for:
          - Debugging
          - Local analysis
          - Migrating to Zep
        
        Returns:
            List of all LearningLogEntry objects, oldest first
        """
        if not self.log_path.exists():
            return []
            
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(LearningLogEntry.model_validate_json(line))
        return entries
