"""LangGraph Graph Assembly for Pipeline Orchestration.

Two graphs:
1. Discovery Graph: Find topics → Grade → Save to Kanban (no loops, no human gates)
2. Production Graph: Research → Script → Visuals → Publish (with Karpathy loop and human review)

The Production Graph contains the conditional Karpathy loop:
  - After scoring, check: score >= 85% OR iterations >= 20?
  - If YES: exit loop → capture learnings → visuals
  - If NO: mutate the draft → re-score → check again

Human Review Gate:
  - After visuals, the graph PAUSES (interrupt)
  - Human reviews and either approves or sends feedback
  - If approved: publish to Notion
  - If rejected: go back to draft node with feedback
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, END, START
from langgraph.pregel import RetryPolicy

from .state import DiscoveryState, ProductionState
from .nodes import (
    # Discovery nodes
    gather_context_node,
    search_web_node,
    generate_topics_node,
    grade_viability_node,
    save_topics_node,
    # Production nodes
    load_learnings_node,
    research_node,
    draft_node,
    score_node,
    mutate_node,
    capture_learning_node,
    visual_node,
    human_review_node,
    publish_notion_node,
    # Error handling
    error_handler_node,
)

logger = logging.getLogger(__name__)

# Retry policy for nodes that make external API calls
LLM_RETRY = RetryPolicy(
    max_attempts=3,
    initial_interval=2.0,     # Wait 2 seconds before first retry
    backoff_factor=2.0,        # Then 4s, then 8s
)

# More aggressive retry for the publish step
PUBLISH_RETRY = RetryPolicy(
    max_attempts=5,
    initial_interval=1.0,
    backoff_factor=3.0,
)


# ============================================================
# DISCOVERY GRAPH
# ============================================================

def _check_error(state) -> Literal["continue", "error"]:
    """Route to error_handler if any node set the error field."""
    if state.get("error"):
        return "error"
    return "continue"


def build_discovery_graph():
    """
    Discovery Graph: Find topics → Grade → Save to Kanban
    
    Flow:
    START → gather_context → search_web → generate_topics → grade_viability → save_topics → END
    
    Every node has error handling via the @pipeline_node decorator.
    If any node fails, the error field gets set and the conditional edge
    routes to error_handler instead of the next node.
    """
    workflow = StateGraph(DiscoveryState)
    
    # Add nodes
    workflow.add_node("gather_context", gather_context_node)
    workflow.add_node("search_web", search_web_node)
    workflow.add_node("generate_topics", generate_topics_node)
    workflow.add_node("grade_viability", grade_viability_node)
    workflow.add_node("save_topics", save_topics_node)
    workflow.add_node("error_handler", error_handler_node)
    
    # Define flow with error checking at each step
    workflow.set_entry_point("gather_context")
    
    workflow.add_conditional_edges("gather_context", _check_error, {
        "continue": "search_web", "error": "error_handler"
    })
    workflow.add_conditional_edges("search_web", _check_error, {
        "continue": "generate_topics", "error": "error_handler"
    })
    workflow.add_conditional_edges("generate_topics", _check_error, {
        "continue": "grade_viability", "error": "error_handler"
    })
    workflow.add_conditional_edges("grade_viability", _check_error, {
        "continue": "save_topics", "error": "error_handler"
    })
    workflow.add_edge("save_topics", END)
    workflow.add_edge("error_handler", END)
    
    return workflow


# ============================================================
# PRODUCTION GRAPH
# ============================================================

def should_continue(state: ProductionState) -> Literal["mutate", "done", "error"]:
    """
    The core Karpathy decision function.
    
    Rules:
    1. If there's an error → route to error handler
    2. If score >= 85% → we have a winner, exit loop
    3. If iterations >= 20 → exhausted attempts, exit loop with best draft
    4. Otherwise → mutate and try again
    """
    if state.get("error"):
        return "error"
    
    score = state.get("evaluation_score", 0)
    iterations = state.get("iteration_count", 0)
    
    # Quality threshold from Phase 3
    if score >= 85:
        return "done"
    if iterations >= 20:
        return "done"
    return "mutate"


def after_review(state: ProductionState) -> Literal["approve", "revise", "error"]:
    """
    Route based on human's decision after reviewing the script.
    """
    if state.get("error"):
        return "error"
    if state.get("approved", False):
        return "approve"
    return "revise"


def build_production_graph():
    """
    Production Graph: Research → Draft → Score → (Mutation Loop) → Visuals → Review → Publish
    
    The Karpathy Loop:
      - After scoring, check: score >= 85% OR iterations >= 20?
      - If YES: exit loop → capture learnings → visuals
      - If NO: mutate the draft → re-score → check again
    
    Human Review Gate:
      - After visuals, the graph PAUSES (interrupt)
      - Human reviews and either approves or sends feedback
      - If approved: publish to Notion
      - If rejected: go back to draft node with feedback
    """
    workflow = StateGraph(ProductionState)
    
    # ── Register nodes ──
    # retry= ensures transient API failures don't kill the pipeline
    workflow.add_node("load_learnings", load_learnings_node, retry=LLM_RETRY)
    workflow.add_node("research", research_node, retry=LLM_RETRY)
    workflow.add_node("draft", draft_node, retry=LLM_RETRY)
    workflow.add_node("score", score_node, retry=LLM_RETRY)
    workflow.add_node("mutate", mutate_node, retry=LLM_RETRY)
    workflow.add_node("capture_learning", capture_learning_node)
    workflow.add_node("visuals", visual_node, retry=LLM_RETRY)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("publish", publish_notion_node, retry=PUBLISH_RETRY)
    workflow.add_node("error_handler", error_handler_node)
    
    # ── Linear flow: Start → Research ──
    workflow.set_entry_point("load_learnings")
    workflow.add_edge("load_learnings", "research")
    workflow.add_edge("research", "draft")
    workflow.add_edge("draft", "score")
    
    # ── Karpathy Loop: Score → Continue? ──
    workflow.add_conditional_edges(
        "score",
        should_continue,
        {
            "mutate": "mutate",
            "done": "capture_learning",
            "error": "error_handler",
        }
    )
    
    # Mutation cycles back to scoring
    workflow.add_edge("mutate", "score")
    
    # ── Post-loop flow ──
    workflow.add_edge("capture_learning", "visuals")
    workflow.add_edge("visuals", "human_review")
    
    # ── Human review decision ──
    workflow.add_conditional_edges(
        "human_review",
        after_review,
        {
            "approve": "publish",
            "revise": "draft",
            "error": "error_handler",
        }
    )
    
    workflow.add_edge("publish", END)
    workflow.add_edge("error_handler", END)
    
    return workflow
