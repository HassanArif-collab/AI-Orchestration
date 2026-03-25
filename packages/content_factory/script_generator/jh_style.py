"""
Johnny Harris Style Generator

Implements the Johnny Harris documentary style patterns:
- Visual-first storytelling
- Hidden mechanism reveal
- Physical anchor hierarchy
- Narrative structures

Johnny Harris style characteristics:
1. Visual anchors (documents, maps, locations)
2. Hidden mechanisms revealed visually
3. Oversimplified narrative deconstruction
4. Emotional connection through human stories
5. Clear cause-effect chains
"""

import json
import re
from typing import Optional

from packages.core.logger import get_logger
from packages.router.client import RouterClient
from packages.content_factory.production.models import ResearchDossier
from .models import DualColumnScript, DualColumnEntry, SectionLabel, VisualType

log = get_logger(__name__)


# ─── Johnny Harris Patterns ──────────────────────────────────────────────────────

JH_HOOK_PATTERNS = [
    "The mainstream narrative about {topic} is wrong. Here's what's really happening.",
    "Everyone thinks {assumption}. But I found something that changes everything.",
    "This {object} tells a story nobody's talking about.",
    "What you're not being told about {topic}...",
    "There's something happening in {location} that explains everything.",
    "The real story behind {topic} isn't what you've heard.",
]

JH_NARRATIVE_STRUCTURES = {
    "hidden_mechanism": {
        "description": "Reveal an invisible system driving visible events",
        "structure": ["HOOK", "ANCHOR", "BRIDGE", "REVEAL", "CONCLUSION"],
        "guidance": "Show the mechanism visually - diagrams, animations, before/after"
    },
    
    "oversimplified_narrative": {
        "description": "Deconstruct a common misconception",
        "structure": ["HOOK", "BRIDGE", "EVIDENCE", "REVEAL", "CONCLUSION"],
        "guidance": "Build contrast between what people believe and what's true"
    },
    
    "hidden_connection": {
        "description": "Connect two seemingly unrelated things",
        "structure": ["HOOK", "ANCHOR_A", "BRIDGE", "ANCHOR_B", "REVEAL", "CONCLUSION"],
        "guidance": "Each anchor supports one side of the connection"
    },
    
    "universal_in_local": {
        "description": "Show how global patterns manifest locally",
        "structure": ["HOOK", "LOCAL_STORY", "BRIDGE", "GLOBAL_PATTERN", "CONCLUSION"],
        "guidance": "Start specific to Pakistani context, expand to broader truth"
    }
}

JH_VISUAL_DIRECTIVES = {
    "talking_head": [
        "Close-up on face, direct address to camera",
        "Walking shot, camera following",
        "Standing at location, gesturing to surroundings"
    ],
    
    "broll": [
        "Slow pan across [specific location]",
        "Aerial shot of [location] at [time of day]",
        "Time-lapse of [process]",
        "Archive footage of [specific event, year]"
    ],
    
    "animation": [
        "Animated map showing [movement/change]",
        "Diagram of [mechanism] appearing piece by piece",
        "Data visualization: [metric] over time",
        "Before/after morph of [transformation]"
    ],
    
    "document": [
        "Close-up of document, highlight relevant section",
        "Pull quote appearing over document",
        "Zoom into specific data point",
        "Side-by-side comparison of two documents"
    ],
    
    "data_viz": [
        "Chart builds: [data points] appear in sequence",
        "Infographic of [complex system]",
        "Map overlay with [data layer]",
        "Animated graph showing [trend]"
    ]
}

JH_ANCHOR_HIERARCHY = {
    1: "Primary source artifacts (original documents, physical evidence)",
    2: "Geographic proof (locations, buildings, landscapes)",
    3: "Expert testimony (interviews, quotes)",
    4: "Data visualizations (charts, graphs)",
    5: "Generic B-roll (stock footage, general images)"
}


# ─── JH Style Generator ──────────────────────────────────────────────────────────

class JHStyleGenerator:
    """
    Generates scripts in the Johnny Harris documentary style.
    
    Usage:
        generator = JHStyleGenerator()
        script = await generator.generate(
            prompt="...",
            dossier=research_dossier,
            complexity=complexity_result
        )
    """
    
    def __init__(self, router_client: RouterClient = None):
        self.router = router_client
    
    async def generate(
        self,
        prompt: str,
        dossier: ResearchDossier = None,
        complexity: dict = None,
        structure_type: str = "hidden_mechanism"
    ) -> DualColumnScript:
        """
        Generate a dual-column script in Johnny Harris style.
        
        Args:
            prompt: The prompt for script generation
            dossier: Research dossier with facts and sources
            complexity: Complexity assessment (determines depth)
            structure_type: Type of narrative structure
        
        Returns:
            DualColumnScript ready for evaluation
        """
        from packages.router.client import RouterClient
        
        # Get structure
        structure = JH_NARRATIVE_STRUCTURES.get(
            structure_type,
            JH_NARRATIVE_STRUCTURES["hidden_mechanism"]
        )
        
        # Build context from research
        research_context = ""
        if dossier:
            research_context = f"""
RESEARCH CONTEXT:
- Topic: {dossier.topic}
- Key Facts: {[f.statement[:100] for f in dossier.facts_and_data[:5]]}
- Physical Anchors: {[a.description[:50] for a in dossier.physical_anchors[:3]]}
- Human Characters: {[c.name for c in dossier.human_characters[:2]]}
"""
        
        # Determine depth from complexity
        depth = complexity.get("depth_level", "moderate") if complexity else "moderate"
        
        system_prompt = self._build_system_prompt(structure, depth)
        user_prompt = f"""
{prompt}

{research_context}

Generate a complete dual-column script in the Johnny Harris style.
The script should be suitable for a Pakistani audience with local context.

Output strictly in JSON format:
{{
    "title": "Video Title",
    "entries": [
        {{
            "section_label": "HOOK|ANCHOR|BRIDGE|REVEAL|CONCLUSION",
            "prose": "Narration text for left column",
            "visual_direction": "Specific visual direction for right column",
            "visual_type": "talking_head|broll|animation|archive|data_viz|soul_moment",
            "duration_estimate_seconds": 30,
            "anchor_hierarchy_level": 1
        }}
    ]
}}
"""
        
        try:
            async with RouterClient() as router:
                response = await router.complete_text(
                    user_prompt,
                    system=system_prompt,
                    max_tokens=4000
                )
                
                # Parse response
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if not match:
                    raise ValueError("Could not extract JSON from response")
                
                data = json.loads(match.group(0))
                
                # Build script
                entries = []
                for item in data.get("entries", []):
                    entries.append(DualColumnEntry(
                        section_label=SectionLabel(item.get("section_label", "BRIDGE")),
                        prose=item.get("prose", ""),
                        visual_direction=item.get("visual_direction", ""),
                        visual_type=VisualType(item.get("visual_type", "broll")),
                        duration_estimate_seconds=item.get("duration_estimate_seconds", 30),
                        anchor_hierarchy_level=item.get("anchor_hierarchy_level", 3)
                    ))
                
                script = DualColumnScript(
                    video_id=f"script_{hash(prompt) % 1000000:06d}",
                    adapted_title=data.get("title", "Untitled"),
                    entries=entries,
                    complexity_depth=depth,
                    complexity_score=complexity.get("score", 1.5) if complexity else 1.5,
                    section_sequence=[e.section_label.value for e in entries]
                )
                
                log.info(f"script_generated: {len(entries)} entries, depth={depth}")
                return script
                
        except Exception as e:
            log.error(f"script_generation_failed: {e}")
            # Return minimal valid script
            return DualColumnScript(
                video_id="error",
                adapted_title="Generation Error",
                entries=[DualColumnEntry(
                    section_label=SectionLabel.HOOK,
                    prose="Script generation failed. Please retry.",
                    visual_direction="Error message",
                    visual_type=VisualType.TALKING_HEAD
                )]
            )
    
    def _build_system_prompt(self, structure: dict, depth: str) -> str:
        """Build the system prompt for script generation."""
        
        depth_guidance = {
            "shallow": "Keep it focused - 3-4 sections maximum. Direct and efficient.",
            "moderate": "Balance depth and clarity. 5-6 sections with good context.",
            "deep": "Full investigative depth. Multiple reveals and thorough context."
        }
        
        return f"""You are generating a script for a Johnny Harris-style investigative documentary.

JOHNNY HARRIS STYLE ESSENTIALS:
1. VISUAL-FIRST: Every narration point must have a corresponding visual
2. HIDDEN MECHANISMS: Reveal invisible systems that drive visible events
3. PHYSICAL ANCHORS: Use tangible evidence (documents, locations, objects)
4. EMOTIONAL CONNECTION: Connect to the audience's daily life
5. CLEAR STRUCTURE: Hook → Investigation → Reveal → Conclusion

NARRATIVE STRUCTURE:
{structure['description']}
Sections: {' → '.join(structure['structure'])}
Guidance: {structure['guidance']}

DEPTH: {depth_guidance.get(depth, depth_guidance['moderate'])}

VISUAL ANCHOR HIERARCHY:
Level 1: Original documents, physical evidence
Level 2: Geographic locations, buildings
Level 3: Expert testimony, interviews
Level 4: Data visualizations
Level 5: Generic B-roll (avoid if possible)

OUTPUT: Valid JSON only. No markdown, no explanations.
"""
