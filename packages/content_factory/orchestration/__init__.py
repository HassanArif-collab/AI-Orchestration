"""
Orchestration System — LangGraph State Machine (Phase 4).

The orchestration system now uses LangGraph for crash-proof, checkpointed
pipeline execution. Each node does ONE thing, ONE time. LangGraph handles
all flow control, conditional edges, and human gates.

TWO GRAPHS:
  1. Discovery Graph: Find topics → Grade → Save to Kanban
  2. Production Graph: Research → Script → Visuals → Publish (with Karpathy loop)

KEY COMPONENTS:
  - state.py: TypedDict definitions for pipeline state
  - nodes.py: Node functions that wrap existing agents
  - graphs.py: Graph assembly with conditional edges
  - thoughts.py: Thought streaming infrastructure
  - checkpointer.py: Supabase PostgreSQL checkpointer

DEPRECATED FILES (kept for reference):
  - master.py: Old orchestration master
  - scheduler.py: Old cron-like job runner
  - synthesis.py: Old weekly learning engine
  - These will be removed after Phase 5 frontend is confirmed working.

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

from .checkpointer import get_checkpointer, close_checkpointer, get_memory_saver
from .graphs import build_discovery_graph, build_production_graph
from .state import DiscoveryState, ProductionState


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
