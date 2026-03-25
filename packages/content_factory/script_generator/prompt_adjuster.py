"""
Prompt Adjuster Module

Adjusts prompts based on evaluation results.
Uses different strategies to improve weak areas.
"""

from typing import Optional

from packages.core.logger import get_logger
from .models import DualColumnScript, SelfEvaluationReport

log = get_logger(__name__)


# ─── Improvement Hints by Criterion ─────────────────────────────────────────────

IMPROVEMENT_HINTS = {
    "H1": """
The hook is not creating enough curiosity. Try these approaches:
- Start with a provocative question: "What if everything you knew about X was wrong?"
- Use a surprising statistic: "In Pakistan, 80% of people believe X, but the truth is..."
- Create a knowledge gap: "There's something happening in [location] that nobody's talking about"
- Use visual contrast in the first frame
""",
    
    "H2": """
The knowledge gap is not clear. Consider:
- Explicitly state what people believe vs what's true
- Use the "Most people think X, but actually Y" pattern
- Make the gap feel personal to the audience
- Hint at the revelation without giving it away
""",
    
    "H3": """
The first 5 seconds aren't compelling enough. Try:
- Cut to the most visually striking moment immediately
- Use a cliffhanger statement: "What I found in [document] changed everything"
- Avoid starting with background - jump straight into the mystery
""",
    
    "V1": """
Not every section can be visualized. Consider:
- Each point needs a corresponding visual direction
- If you can't show it, don't say it
- Use visual metaphors for abstract concepts
""",
    
    "V2": """
Visual directions are too vague. Be more specific:
- Instead of "Show a map" → "Animated map of Pakistan with red zones highlighting X"
- Instead of "Archive footage" → "BBC archive from 1971 showing [specific event]"
- Include timing: "Hold for 3 seconds on this graphic"
""",
    
    "N1": """
The narrative doesn't progress logically. Consider:
- Each section should answer a question raised by the previous
- Use the "And then..." test: can you follow the story?
- Build tension progressively toward the reveal
""",
    
    "N2": """
Transitions are abrupt. Try:
- Use bridging phrases: "But this wasn't the whole story..."
- Let the visual connect the sections
- End each section with a question that the next section answers
""",
    
    "E1": """
Claims lack supporting evidence. Add:
- Specific source citations in the narration
- Data points with attribution
- Quotes from credible sources
""",
    
    "E2": """
Sources are not credible or current. Consider:
- Use recent reports (2023-2025)
- Cite authoritative institutions
- Avoid Wikipedia as primary source
- Use Pakistani sources where relevant (Dawn, The News, government reports)
""",
    
    "A1": """
Not relevant enough to Pakistani audience. Consider:
- Connect to Pakistani current events or social issues
- Use Pakistani examples and case studies
- Explain implications for ordinary Pakistanis
- Reference Pakistani institutions or figures
""",
    
    "A2": """
Local context is missing. Add:
- Pakistani statistics and data
- Local terminology and references
- Pakistani expert quotes
- Historical context relevant to Pakistan
""",
}


# ─── Prompt Adjuster ─────────────────────────────────────────────────────────────

class PromptAdjuster:
    """
    Adjusts prompts based on evaluation gaps.
    
    Uses different strategies when stagnation is detected.
    """
    
    def __init__(self):
        self.adjustment_count = {}
    
    def adjust(
        self,
        current_prompt: str,
        weak_areas: list[str],
        detailed_scores: dict = None,
        iteration: int = 0,
        previous_script: DualColumnScript = None
    ) -> str:
        """
        Generate an adjusted prompt targeting weak areas.
        
        Args:
            current_prompt: The previous prompt
            weak_areas: List of criterion IDs that scored low
            detailed_scores: Detailed score breakdown
            iteration: Current iteration number
            previous_script: The script from previous iteration
        
        Returns:
            Adjusted prompt with targeted improvements
        """
        # Gather hints for weak areas
        hints = []
        for area in weak_areas:
            hint = IMPROVEMENT_HINTS.get(area, "")
            if hint:
                hints.append(f"### {area}:{hint}")
        
        # Build adjustment block
        adjustment_block = "\n".join(hints) if hints else "No specific adjustments needed."
        
        # Track adjustments
        for area in weak_areas:
            self.adjustment_count[area] = self.adjustment_count.get(area, 0) + 1
        
        # Build improved prompt
        improved_prompt = f"""
{current_prompt}

═══════════════════════════════════════════════════════════════
ITERATION {iteration} REFINEMENT
═══════════════════════════════════════════════════════════════

Previous attempt scored low on: {', '.join(weak_areas)}

SPECIFIC IMPROVEMENTS NEEDED:
{adjustment_block}

CRITICAL: You MUST address these weaknesses. Score must reach 85%.

Previous script summary (do NOT repeat the same mistakes):
{self._summarize_script(previous_script) if previous_script else "N/A - first iteration"}
"""
        
        log.info(f"prompt_adjusted: iteration={iteration}, weak_areas={weak_areas}")
        return improved_prompt
    
    def try_alternative_strategy(
        self,
        current_prompt: str,
        weak_areas: list[str]
    ) -> str:
        """
        When stagnation is detected, try a completely different approach.
        
        This is called when scores aren't improving after several iterations.
        """
        strategies = [
            self._strategy_change_angle,
            self._strategy_simplify_structure,
            self._strategy_add_emotional_layer,
            self._strategy_focus_on_visuals,
            self._strategy_start_from_scratch,
        ]
        
        # Choose strategy based on weak areas
        strategy_index = len(weak_areas) % len(strategies)
        strategy = strategies[strategy_index]
        
        log.info(f"alternative_strategy: using strategy {strategy_index + 1}")
        return strategy(current_prompt, weak_areas)
    
    def _summarize_script(self, script: DualColumnScript) -> str:
        """Create a brief summary of previous script."""
        if not script or not script.entries:
            return "No previous script"
        
        sections = [e.section_label.value for e in script.entries[:5]]
        return f"Sections: {' → '.join(sections)}. Score: {script.production_readiness_score:.0f}%"
    
    def _strategy_change_angle(self, prompt: str, weak_areas: list[str]) -> str:
        """Change the angle of the story."""
        return f"""
{prompt}

⚠️ STRATEGY CHANGE: APPROACH FROM DIFFERENT ANGLE

Instead of the current approach, try:
- Start from a different character's perspective
- Lead with a different question
- Use a counter-intuitive framing

The core facts remain the same, but the narrative path changes.
"""
    
    def _strategy_simplify_structure(self, prompt: str, weak_areas: list[str]) -> str:
        """Simplify the narrative structure."""
        return f"""
{prompt}

⚠️ STRATEGY CHANGE: SIMPLIFY STRUCTURE

The current structure may be too complex. Try:
- Reduce to 3-4 main sections instead of 5+
- One clear reveal instead of multiple
- Clearer cause-effect chain
- Less tangential information

Simple and clear beats complex and confusing.
"""
    
    def _strategy_add_emotional_layer(self, prompt: str, weak_areas: list[str]) -> str:
        """Add emotional depth to the story."""
        return f"""
{prompt}

⚠️ STRATEGY CHANGE: ADD EMOTIONAL LAYER

The script may be too informational. Add:
- A human character whose story illustrates the issue
- Personal stakes for the audience
- Moments of surprise, concern, or hope
- Connection to audience's daily life

Make them feel something, not just learn something.
"""
    
    def _strategy_focus_on_visuals(self, prompt: str, weak_areas: list[str]) -> str:
        """Rebuild with visual storytelling priority."""
        return f"""
{prompt}

⚠️ STRATEGY CHANGE: VISUAL-FIRST APPROACH

Start by designing the visual sequence, then write narration to match:
- What visuals are absolutely available?
- What can be shown that proves the point?
- Build the script around visual evidence

If you can't show it, reconsider including it.
"""
    
    def _strategy_start_from_scratch(self, prompt: str, weak_areas: list[str]) -> str:
        """Start fresh with just the core thesis."""
        return f"""
⚠️ STRATEGY CHANGE: FRESH START

The current approach isn't working. Start fresh:

1. What is the ONE thing the viewer must understand?
2. What is the ONE piece of evidence that proves it?
3. What is the ONE hook that will make them care?

Build from these three things only. Add complexity only where needed.

Core facts from research are still valid - just the presentation changes.
"""
