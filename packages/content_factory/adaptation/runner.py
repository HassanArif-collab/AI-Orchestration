"""Pipeline Runner orchestrator for the Adaptation Engine.

Runs all four stages sequentially and handles state transitions.
"""

import uuid

from packages.core.logger import get_logger
from packages.router.client import RouterClient

from ..error_log import ErrorLogger
from ..models import AdaptedScript
from ..source_library import SourceVideoLibrary

from .stage1_extraction import stage1_extract
from .stage2_structural import stage2_analyze
from .stage3_localization import stage3_localize
from .stage4_script import stage4_generate

logger = get_logger(__name__)


async def run_adaptation(url: str, cycle_id: str | None = None) -> AdaptedScript | None:
    """Run the complete 4-stage adaptation pipeline.

    Args:
        url: YouTube video URL.
        cycle_id: Optional tracking ID for logs.

    Returns:
        AdaptedScript on success, None on pipeline failure.
    """
    cycle_id = cycle_id or str(uuid.uuid4())
    logger.info(f"adaptation_pipeline_started: {cycle_id} — {url}")

    # Initialize shared services
    error_logger = ErrorLogger()
    library = SourceVideoLibrary()

    async with RouterClient() as router_client:

        # Stage 1
        extraction = await stage1_extract(url, None, library, error_logger, cycle_id)
        if not extraction:
            return None

        # Stage 2
        smap = await stage2_analyze(extraction, router_client, library, error_logger, cycle_id)
        if not smap:
            return None

        # Stage 3
        lmap = await stage3_localize(smap, extraction, router_client, error_logger, cycle_id)
        if not lmap:
            return None

        # Stage 4
        script = await stage4_generate(smap, lmap, router_client, library, error_logger, cycle_id)
        if not script:
            return None

    logger.info(f"adaptation_pipeline_completed: {cycle_id} — {url}")
    return script
