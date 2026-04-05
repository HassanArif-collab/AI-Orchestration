"""
Orchestration System — LangGraph State Machine.

Crash-proof, checkpointed pipeline execution. Each node does ONE thing,
ONE time. LangGraph handles all flow control, conditional edges, and
human gates.

TWO GRAPHS:
  1. Discovery Graph: Find topics → Grade → Save to Kanban
  2. Production Graph: Research → Script → Visuals → Publish (with Karpathy loop)

KEY COMPONENTS:
  - state.py: TypedDict definitions for pipeline state
  - nodes.py: Node functions that wrap existing agents
  - graphs.py: Graph assembly with conditional edges
  - thoughts.py: Thought streaming infrastructure
  - checkpointer.py: Supabase PostgreSQL checkpointer

USAGE:
    from packages.content_factory.orchestration import (
        get_discovery_graph,
        get_production_graph,
        close_checkpointer,
    )
    
    # Get compiled graphs
    discovery = await get_discovery_graph()
    production = await get_production_graph()
    
    # Run production pipeline
    result = await production.ainvoke(initial_state, config)
    
    # Cleanup on shutdown
    await close_checkpointer()
"""

# Non-langgraph imports (pure Python, always available)
from .state import DiscoveryState, ProductionState
from .thoughts import report_thought, pipeline_node, update_card_stage
from .checkpointer import get_checkpointer, close_checkpointer, get_memory_saver

# Lazy imports for graph assembly (requires langgraph at runtime)
def build_discovery_graph():
    """Import and return the discovery graph builder. Requires langgraph."""
    from .graphs import build_discovery_graph as _build
    return _build()

def build_production_graph():
    """Import and return the production graph builder. Requires langgraph."""
    from .graphs import build_production_graph as _build
    return _build()


async def get_discovery_graph():
    """
    Returns a compiled discovery graph with Supabase checkpointing.
    Call this once at app startup, reuse the compiled graph.
    """
    checkpointer = await get_checkpointer()
    workflow = build_discovery_graph()
    return workflow.compile(checkpointer=checkpointer)


async def get_production_graph():
    """
    Returns a compiled production graph with Supabase checkpointing.
    
    The interrupt_before=["human_review"] tells LangGraph to save 
    a checkpoint BEFORE entering the human_review node, so the 
    interrupt() call inside the node can cleanly pause execution.
    """
    checkpointer = await get_checkpointer()
    workflow = build_production_graph()
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"],
    )


# For testing without Supabase
def get_discovery_graph_memory():
    """Returns a discovery graph with MemorySaver for testing."""
    checkpointer = get_memory_saver()
    workflow = build_discovery_graph()
    return workflow.compile(checkpointer=checkpointer)


def get_production_graph_memory():
    """Returns a production graph with MemorySaver for testing."""
    checkpointer = get_memory_saver()
    workflow = build_production_graph()
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"],
    )


__all__ = [
    # State definitions
    "DiscoveryState",
    "ProductionState",
    # Graph builders
    "build_discovery_graph",
    "build_production_graph",
    # Compiled graphs (with Supabase)
    "get_discovery_graph",
    "get_production_graph",
    # Memory graphs (for testing)
    "get_discovery_graph_memory",
    "get_production_graph_memory",
    # Checkpointer
    "get_checkpointer",
    "close_checkpointer",
    "get_memory_saver",
]
