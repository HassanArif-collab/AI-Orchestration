"""Phase 4 Auto-Research Loop: Learning Log.

Logs mutation experiments, zone tracking, and evolutionary progression.
Stored as JSON Lines for easy parsing by analysis tools.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel

from packages.core.logger import get_logger
from packages.memory.client import ZepMemoryClient
from packages.core.config import get_settings

logger = get_logger(__name__)

DEFAULT_LOG_PATH = "packages/data/learning_log.jsonl"


class LearningLogEntry(BaseModel):
    """A record of one mutation cycle."""
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
    """JSONL logger for tracking Auto-Research Loop experiments."""

    def __init__(self, log_path: str = DEFAULT_LOG_PATH) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.zep_client = ZepMemoryClient()
        self.learning_user_id = get_settings().ZEP_LEARNING_USER_ID
        self.zep_session_id = f"{self.learning_user_id}_session"

    def log_experiment(self, entry: LearningLogEntry) -> None:
        """Append an experiment record to the log."""
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
            
        # Zep dual-write
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
        self.zep_client.add_facts(session_id=self.zep_session_id, facts=[{"fact": content, **metadata}])

        if entry.beat_baseline:
            logger.info(f"experiment_success: Zone {entry.mutation_zone} improved score from {entry.baseline_score:.1f}% to {entry.challenger_score:.1f}%")
        else:
            logger.info(f"experiment_failure: Zone {entry.mutation_zone} failed to beat {entry.baseline_score:.1f}%")

    def read_logs(self) -> list[LearningLogEntry]:
        """Read all experiment logs."""
        if not self.log_path.exists():
            return []
            
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(LearningLogEntry.model_validate_json(line))
        return entries
