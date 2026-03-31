"""Error logging for the Content Factory adaptation pipeline.

All errors and warnings from all stages are logged in a consistent format
that Phase 4's Auto Research Loop can read and process.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from packages.core.logger import get_logger

from .models import AdaptationError, AdaptationStage
from typing import Union

logger = get_logger(__name__)

# Default log file path
DEFAULT_LOG_PATH = "packages/data/adaptation_errors.jsonl"


class ErrorLogger:
    """Structured error/warning logger for adaptation pipeline.

    Writes JSON Lines format so each entry is independently parseable.
    Errors (pipeline-stopping) and warnings (pipeline-continuing) are
    stored in the same file with a severity field to distinguish them.
    """

    def __init__(self, log_path: str = DEFAULT_LOG_PATH) -> None:
        """Initialize the error logger.

        Args:
            log_path: Path to the JSONL log file.
        """
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_error(
        self,
        production_cycle_id: str,
        stage_number: Union[int, AdaptationStage],
        error_type: str,
        description: str,
        content_element: str = "",
        pipeline_stopped: bool = True,
    ) -> AdaptationError:
        """Log a pipeline error (stops pipeline).

        Args:
            production_cycle_id: Unique ID for this adaptation run.
            stage_number: Stage where error occurred (use AdaptationStage enum).
            error_type: Error type name from the spec.
            description: Human-readable error description.
            content_element: The specific content that caused the error.
            pipeline_stopped: Whether the pipeline was halted.

        Returns:
            The logged AdaptationError instance.
        """
        entry = AdaptationError(
            production_cycle_id=production_cycle_id,
            stage_number=stage_number,
            error_type=error_type,
            content_element=content_element,
            description=description,
            pipeline_stopped=pipeline_stopped,
            severity="error",
        )
        self._write(entry)
        logger.error(
            f"adaptation_error: stage={stage_number} type={error_type} "
            f"stopped={pipeline_stopped} — {description}"
        )
        return entry

    def log_warning(
        self,
        production_cycle_id: str,
        stage_number: Union[int, AdaptationStage],
        error_type: str,
        description: str,
        content_element: str = "",
    ) -> AdaptationError:
        """Log a pipeline warning (pipeline continues).

        Args:
            production_cycle_id: Unique ID for this adaptation run.
            stage_number: Stage where warning occurred (use AdaptationStage enum).
            error_type: Warning type name.
            description: Human-readable warning description.
            content_element: The specific content that triggered the warning.

        Returns:
            The logged AdaptationError instance.
        """
        entry = AdaptationError(
            production_cycle_id=production_cycle_id,
            stage_number=stage_number,
            error_type=error_type,
            content_element=content_element,
            description=description,
            pipeline_stopped=False,
            severity="warning",
        )
        self._write(entry)
        logger.warning(
            f"adaptation_warning: stage={stage_number} type={error_type} — {description}"
        )
        return entry

    def _write(self, entry: AdaptationError) -> None:
        """Append an entry to the JSONL log file."""
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

    def read_errors(
        self,
        production_cycle_id: str | None = None,
        severity: str | None = None,
    ) -> list[AdaptationError]:
        """Read errors from the log, optionally filtered.

        Args:
            production_cycle_id: Filter by cycle ID.
            severity: Filter by 'error' or 'warning'.

        Returns:
            List of matching AdaptationError entries.
        """
        if not self.log_path.exists():
            return []

        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = AdaptationError.model_validate_json(line)
                if production_cycle_id and entry.production_cycle_id != production_cycle_id:
                    continue
                if severity and entry.severity != severity:
                    continue
                entries.append(entry)
        return entries
