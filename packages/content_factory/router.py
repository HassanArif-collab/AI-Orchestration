"""
Content Creation Router — The Central Dispatcher.

Reads content_type from a TopicBrief and routes to the correct pipeline:
  "adaptation" → Mode A: run_adaptation() from adaptation/runner.py
  "original"   → Mode B: run_production_workflow() from production/workflow.py

Both paths return an AdaptedScript which then feeds the ExperimentLoop.

Usage:
    router = ContentCreationRouter()
    script = await router.route(topic_brief)
    refined_script = await router.run_experiment_loop(script)
"""

from packages.core.config import get_settings
from packages.core.logger import get_logger
from packages.content_factory.topic_finder.models import TopicBrief
from packages.content_factory.models import AdaptedScript, DualColumnEntry, SectionLabel
from packages.content_factory.evaluation.loop import ExperimentLoop

logger = get_logger(__name__)

DEV_MODE = get_settings().PIPELINE_DEV_MODE


class ContentCreationRouter:
    """Routes topic briefs to the correct content creation pipeline."""

    async def route(self, brief: TopicBrief) -> AdaptedScript | None:
        """Route a TopicBrief to Mode A (adaptation) or Mode B (original)."""
        logger.info(f"routing: brief_id={brief.brief_id} content_type={brief.content_type}")

        if brief.content_type == "adaptation":
            return await self._run_adaptation_mode(brief)
        else:
            return await self._run_original_mode(brief)

    async def _run_adaptation_mode(self, brief: TopicBrief) -> AdaptedScript | None:
        """Mode A: Adapt a JH video for Pakistani context."""
        from packages.content_factory.adaptation.runner import run_adaptation

        source_url = brief.adaptation_source_video_id
        if not source_url:
            logger.error("adaptation_mode_missing_source_video_id")
            return None

        if not source_url.startswith("http"):
            source_url = f"https://www.youtube.com/watch?v={source_url}"

        if DEV_MODE:
            return _mock_adapted_script(brief)

        return await run_adaptation(source_url, cycle_id=brief.brief_id)

    async def _run_original_mode(self, brief: TopicBrief) -> AdaptedScript | None:
        """Mode B: Original content using Researcher + Visual Director + Writer."""
        from packages.content_factory.production.workflow import (
            RoundBasedProductionWorkflow, VideoIdea
        )

        if DEV_MODE:
            return _mock_adapted_script(brief)

        idea = VideoIdea(
            topic=brief.topic_statement,
            genre_id=brief.genre_id,
            target_audience="Pakistani",
            special_instructions=f"Big question: {brief.big_question}. "
                                 f"Mainstream assumption to challenge: {brief.mainstream_assumption}",
        )
        workflow = RoundBasedProductionWorkflow()
        return await workflow.run(idea)

    async def run_experiment_loop(
        self,
        script: AdaptedScript,
        max_iterations: int = 20,
        threshold: float = 85.0,
        run_id: str | None = None,
    ) -> AdaptedScript:
        """Run the self-correction Loop on any script (Mode A or Mode B).

        Args:
            script: The initial script to evolve.
            max_iterations: Maximum iterations (default: 20).
            threshold: Target score threshold (default: 85.0).
            run_id: Optional pipeline run ID for iteration logging.

        Returns:
            The best script found after evolution.
        """
        from packages.router.client import RouterClient

        if DEV_MODE:
            logger.info("experiment_loop_skipped_dev_mode")
            return script

        loop = ExperimentLoop()
        async with RouterClient() as router_client:
            return await loop.run_iterations(
                script=script,
                iterations=max_iterations,
                router_client=router_client,
                run_id=run_id,
            )

    def _find_structural_reference(self, genre_id: str):
        """Find the best JH reference video for this genre from SourceVideoLibrary."""
        from packages.content_factory.source_library import SourceVideoLibrary
        library = SourceVideoLibrary()
        refs = library.find_by_genre(genre_id, limit=1)
        return refs[0] if refs else None


def _mock_adapted_script(brief: TopicBrief) -> AdaptedScript:
    """Return a valid mock AdaptedScript for dev/test mode."""
    import uuid
    return AdaptedScript(
        video_id=f"mock_{uuid.uuid4().hex[:8]}",
        source_video_id="mock_source",
        adapted_title=f"Mock: {brief.topic_statement[:60]}",
        genre=brief.genre_id,
        entries=[
            DualColumnEntry(
                section_label=SectionLabel.HOOK,
                prose="Every month, millions face a problem nobody talks about.",
                visual_direction="Wide shot of a busy street in Karachi.",
            ),
            DualColumnEntry(
                section_label=SectionLabel.ANCHOR,
                prose="Here is the specific thing that shows it.",
                visual_direction="Close-up of a physical document or object.",
            ),
            DualColumnEntry(
                section_label=SectionLabel.CONCLUSION,
                prose="And that is why this matters today.",
                visual_direction="Pull back to wide shot, presenter to camera.",
            ),
        ],
        production_readiness_score=0.0,
    )
