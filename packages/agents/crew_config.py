"""CrewAI Configuration and Factory Functions — Infrastructure Bridge.

This module is the BRIDGE between the pipeline infrastructure (packages/agents/)
and the CrewAI-based content creation agents (packages/content_factory/production/).

CURRENT STATUS:
  The functions here (create_research_crew, create_script_crew, create_visual_crew)
  are skeleton implementations with TODOs. They exist to provide a consistent
  interface for the pipeline runner to call without knowing whether CrewAI
  is installed.

  The REAL CrewAI agents are in packages/content_factory/production/agents.py
  and are called directly from the RoundBasedProductionWorkflow.

CREWAI_AVAILABLE FLAG:
  Imported by packages/agents/__init__.py and exposed as a module-level flag.
  Check this before calling any CrewAI-dependent code:
    from packages.agents import CREWAI_AVAILABLE
    if CREWAI_AVAILABLE:
        crew = create_research_crew(topic)

WHEN TO USE THIS vs production/agents.py:
  This module: pipeline infrastructure that needs crew-level orchestration
  production/agents.py: Mode B original content creation (the real CrewAI work)

TODO: Wire these skeleton functions to call production/agents.py so the
pipeline infrastructure can trigger Mode B through a consistent interface.
"""

from typing import Any

# Try to import CrewAI, but make it optional
try:
    from crewai import Agent, Task, Crew

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False


def create_research_crew(topic: str) -> Any:
    """Create a CrewAI crew for the research stage.

    This is a SKELETON IMPLEMENTATION. The actual research crew is
    created in packages/content_factory/production/agents.py: create_researcher()
    
    Args:
        topic: Research topic

    Returns:
        Crew object (or placeholder dict if CrewAI not available)
    
    TODO: Connect to RoundBasedProductionWorkflow._round_research()
    """
    if CREWAI_AVAILABLE:
        # TODO: Implement with actual CrewAI crew
        # Skills will be loaded from data/skills/researcher.md
        agent = Agent(
            role="Researcher",
            goal="Research the given topic thoroughly",
            backstory="Expert researcher with deep domain knowledge",
            verbose=True,
        )
        task = Task(
            description=f"Research the following topic: {topic}",
            agent=agent,
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    # Return placeholder when CrewAI is not available
    return {"crew": "research", "topic": topic, "status": "skeleton"}


def create_script_crew(research: dict) -> Any:
    """Create a CrewAI crew for script writing.

    This is a SKELETON IMPLEMENTATION. The actual writer crew is
    created in packages/content_factory/production/agents.py: create_script_agent()

    Args:
        research: Research data from research stage

    Returns:
        Crew object (or placeholder dict if CrewAI not available)
    
    TODO: Connect to RoundBasedProductionWorkflow._round_script_opening()
    """
    if CREWAI_AVAILABLE:
        # TODO: Implement with actual CrewAI crew
        agent = Agent(
            role="Script Writer",
            goal="Write an engaging video script",
            backstory="Experienced YouTube script writer",
            verbose=True,
        )
        task = Task(
            description=f"Write a script based on this research: {research}",
            agent=agent,
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    return {"crew": "script", "research": research, "status": "skeleton"}


def create_visual_crew(script: dict) -> Any:
    """Create a CrewAI crew for visual planning.

    This is a SKELETON IMPLEMENTATION. The actual visual crew is
    created in packages/content_factory/production/agents.py: create_visual_agent()

    Args:
        script: Script data for visual planning

    Returns:
        Crew object (or placeholder dict if CrewAI not available)
    
    TODO: Connect to Visual Director agent from production/agents.py
    """
    if CREWAI_AVAILABLE:
        # TODO: Implement with actual CrewAI crew
        agent = Agent(
            role="Visual Planner",
            goal="Plan engaging visuals for the video",
            backstory="Expert in video production and visual storytelling",
            verbose=True,
        )
        task = Task(
            description=f"Plan visuals for this script: {script}",
            agent=agent,
        )
        return Crew(agents=[agent], tasks=[task], verbose=True)

    return {"crew": "visual", "script": script, "status": "skeleton"}
