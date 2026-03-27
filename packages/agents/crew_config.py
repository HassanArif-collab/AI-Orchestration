"""CrewAI Configuration and Factory Functions — Infrastructure Bridge.

This module is the BRIDGE between the pipeline infrastructure (packages/agents/)
and the CrewAI-based content creation agents (packages/content_factory/production/).

CURRENT STATUS:
  The functions here (create_research_crew, create_script_crew, create_visual_crew)
  create real CrewAI crews using agents from packages/content_factory/production/agents.py.

CREWAI_AVAILABLE FLAG:
  Imported by packages/agents/__init__.py and exposed as a module-level flag.
  Check this before calling any CrewAI-dependent code:
    from packages.agents import CREWAI_AVAILABLE
    if CREWAI_AVAILABLE:
        crew = create_research_crew(topic)

WHEN TO USE THIS vs production/agents.py:
  This module: pipeline infrastructure that needs crew-level orchestration
  production/agents.py: Mode B original content creation (the real CrewAI work)
"""

from typing import Any

# Try to import CrewAI, but make it optional
try:
    from crewai import Task, Crew, Process

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False


def create_research_crew(topic: str) -> Any:
    """Create a CrewAI crew for the research stage.

    Uses the real Researcher agent from packages/content_factory/production/agents.py.

    Args:
        topic: Research topic

    Returns:
        Crew object when CrewAI is available, None otherwise
    """
    if not CREWAI_AVAILABLE:
        return None

    from packages.content_factory.production.agents import create_researcher
    from crewai import Task, Crew, Process

    researcher = create_researcher(architectural_references=[])
    task = Task(
        description=f"Research '{topic}': find 3+ physical anchors, one human character, "
        "evidence against mainstream narrative. Output structured markdown dossier.",
        expected_output="Structured markdown research dossier.",
        agent=researcher,
    )
    return Crew(agents=[researcher], tasks=[task], process=Process.sequential, verbose=False)


def create_script_crew(research: dict) -> Any:
    """Create a CrewAI crew for script writing.

    Uses the real Script Agent from packages/content_factory/production/agents.py.

    Args:
        research: Research data from research stage

    Returns:
        Crew object when CrewAI is available, None otherwise
    """
    if not CREWAI_AVAILABLE:
        return None

    from packages.content_factory.production.agents import create_script_agent
    from crewai import Task, Crew, Process

    writer = create_script_agent()
    topic = research.get("topic", "the topic") if isinstance(research, dict) else str(research)
    task = Task(
        description=f"Write dual-column documentary script for '{topic}'. "
        "Output strictly valid JSON matching AdaptedScript schema.",
        expected_output="JSON object matching AdaptedScript schema.",
        agent=writer,
    )
    return Crew(agents=[writer], tasks=[task], process=Process.sequential, verbose=False)


def create_visual_crew(script: dict) -> Any:
    """Create a CrewAI crew for visual planning.

    Uses the real Visual Agent from packages/content_factory/production/agents.py.

    Args:
        script: Script data for visual planning

    Returns:
        Crew object when CrewAI is available, None otherwise
    """
    if not CREWAI_AVAILABLE:
        return None

    from packages.content_factory.production.agents import create_visual_agent
    from crewai import Task, Crew, Process

    visual = create_visual_agent()
    title = script.get("adapted_title", "the video") if isinstance(script, dict) else str(script)
    task = Task(
        description=f"Plan visuals for '{title}'. Assign visual types and anchor hierarchy levels.",
        expected_output="Sequence of visual directions.",
        agent=visual,
    )
    return Crew(agents=[visual], tasks=[task], process=Process.sequential, verbose=False)
