"""Phase 3 Core Production Agents.

Provides the Researcher, VisualAgent, and ScriptAgent definitions
using CrewAI. These agents produce *original* Pakistani content
using Johnny Harris strategies, rather than adapting his videos.
"""

from crewai import Agent

from packages.core.logger import get_logger
from ..models import SourceVideoRecord

logger = get_logger(__name__)


def create_researcher(architectural_references: list[SourceVideoRecord]) -> Agent:
    """Create the Researcher Agent.
    
    The Researcher finds raw facts, contradicting evidence, and human characters
    to illustrate the macro problem. It is explicitly instructed to avoid narrative framing.
    
    Args:
        architectural_references: Related Harris videos from Phase 2 Source Video Library
            to establish structural expectations.
    """
    ref_list = "\n".join([f"- {r.title} ({r.genre}): {r.big_question}" for r in architectural_references])
    
    system_prompt = f\"\"\"
    You are an elite investigative researcher building the foundation for a Johnny Harris-style documentary.
    Your job is to uncover raw truth, tangible physical evidence, and human characters.
    
    CRITICAL RULE: Do NOT write narrative. Do NOT write script prose. You are finding facts.
    You must find:
    1. Tangible physical objects, historical documents, or specific geographic locations (Anchors).
    2. A specific human character whose story illustrates the macro problem.
    3. Evidence that contradicts or complicates the mainstream narrative.
    
    Here are the architectural references for the genre you are researching. Notice how they 
    frame their 'Big Questions':
    {ref_list}
    \"\"\"

    return Agent(
        role="Investigative Researcher",
        goal="Uncover raw facts, physical evidence, and human stories that challenge conventional wisdom.",
        backstory=system_prompt,
        allow_delegation=False,
        verbose=True
    )


def create_visual_agent() -> Agent:
    """Create the Visual Agent.
    
    The Visual Agent enforces the Anchor Substitution Hierarchy and strictly
    separates visual evidence from the narrative.
    """
    system_prompt = \"\"\"
    You are the Visual Director for a Johnny Harris-style documentary.
    You define the visual backbone of the story. You do NOT write narration.
    
    Your job is to identify what the camera sees. You must use the Anchor Substitution Hierarchy:
    Level 1: Primary Source Artifacts (Best)
    Level 2: Geographic Proof
    Level 3: Expert Deposition
    Level 4: Abstract Data Visualization
    Level 5: Illustrative Metaphor (Worst - avoid if possible)
    
    For every piece of research provided, you must assign a visual type (talking_head, broll, animation, archive, data_viz, soul_moment) 
    and write specific, executable visual directions. 
    Ensure soul moments are clearly separated from evidence moments.
    \"\"\"

    return Agent(
        role="Visual Director",
        goal="Translate raw research into a sequence of compelling, hierarchy-compliant visual anchors.",
        backstory=system_prompt,
        allow_delegation=False,
        verbose=True
    )


def create_script_agent() -> Agent:
    """Create the Script Agent.
    
    The Script Agent writes the spoken narration using the Phase 1 Style Reference rules.
    """
    system_prompt = \"\"\"
    You are the Lead Writer for a Johnny Harris-style documentary.
    Your job is to write the spoken narration (the prose). 
    
    You MUST obey these rules perfectly:
    1. Every sentence must contain a clear agent performing a visible action (Active Voice).
    2. NO abstract nominalizations (words that describe concepts rather than actions).
    3. The tone must be "friend explaining something at a coffee table".
    4. NO jargon that requires prior domain knowledge.
    5. The viewer MUST be able to form a mental image while hearing every sentence.
    6. Tone calibration: Do not be condescending to the Pakistani audience, and do not assume Western cultural familiarity.
    
    You will take the research and the visual plan and merge them into a Dual-Column script.
    \"\"\"

    return Agent(
        role="Lead Writer",
        goal="Write compelling, active, jargon-free narration that pairs perfectly with the visual plan.",
        backstory=system_prompt,
        allow_delegation=False,
        verbose=True
    )
