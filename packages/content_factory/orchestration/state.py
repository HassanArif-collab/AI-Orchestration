"""LangGraph State Definitions for Pipeline Orchestration.

This module defines the single source of truth for ALL data flowing through
the pipeline. Every node reads from state and writes back to state.

Two separate states for two separate graphs:
- DiscoveryState: Find topics → Grade → Save to Kanban
- ProductionState: Research → Script → Visuals → Publish (with Karpathy loop)

LangGraph snapshots state after every node transition, making the pipeline
crash-proof. If the server dies at iteration 14 of 20, restart picks up
exactly where it left off.

Design decisions:
1. Two separate states/graphs: Discovery and Production are independent workflows.
   Merging them would create a monolithic state that's hard to debug.

2. best_draft + best_score tracking: The old loop only kept "current" draft.
   If iteration 20 scores 60% but iteration 12 scored 78%, we want the 78% draft.

3. evaluation_feedback is separate from evaluation_score: The scorer outputs
   BOTH a number and text feedback. The mutator needs the text feedback to
   know what to fix. The conditional edge needs the number to decide whether to loop.

4. error field: Instead of crashing the graph, nodes write errors here.
   A conditional edge checks for errors and routes to the error handler.
"""

from typing import TypedDict, Optional


class DiscoveryState(TypedDict):
    """State for the Topic Discovery graph.
    
    Flow: gather_context → search_web → generate_topics → grade_viability → save_topics
    
    This graph has NO loops and NO human gates. It runs once and dumps
    topic cards into Kanban Column 2 (Suggested Topics).
    """
    # Identity
    card_id: str
    
    # Inputs
    seed_hint: Optional[str]           # Optional human hint like "AI in Pakistan"
    
    # Zep Memory (Cross-Script Intelligence)
    zep_context: str                    # Past audience data from Zep memory
    
    # Research Phase
    search_results: list                # Raw Exa.ai search results
    
    # Generation Phase
    generated_topics: list              # List of topic dicts with titles/descriptions
    
    # Grading Phase
    graded_topics: list                 # Topics that passed 17-question viability
    
    # Pipeline Control
    pipeline_status: str                # "discovering", "grading", "complete", "error"
    error: Optional[str]               # Error message if something failed


class ProductionState(TypedDict):
    """State for the Production Pipeline graph.
    
    Flow:
    START → load_learnings → research → draft → score → {should_continue?}
                                                        ├── "mutate" → mutate → score (CYCLE)
                                                        ├── "done" → capture_learning → visuals → human_review ⏸️
                                                        │                                           ├── "approve" → publish → END
                                                        │                                           └── "revise" → draft (CYCLE)
                                                        └── "error" → error_handler → END
    
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
    # Identity
    card_id: str
    
    # Inputs
    topic_brief: dict                   # The approved topic from discovery
    
    # ─── Research Phase ──────────────────────────────────────────────────────
    research_dossier: str               # Full research text
    research_sources: list              # URLs and titles of sources
    
    # ─── Zep Learning (Cross-Script Intelligence) ─────────────────────────────
    zep_learnings: str                  # Past winning mutations loaded from Zep
    
    # ─── Script Evolution (Karpathy Loop) ─────────────────────────────────────
    current_draft: str                  # The draft being evaluated RIGHT NOW
    best_draft: str                     # Highest-scoring draft across ALL iterations
    best_score: int                     # Score of best_draft (0-100)
    evaluation_score: int               # Score of current_draft (0-100)
    evaluation_feedback: str            # What the scorer says needs improvement
    iteration_count: int                # Current iteration number (0-20)
    
    # ─── Visual Planning ──────────────────────────────────────────────────────
    visual_plan: str                    # Simple text visual cues (from Phase 2d)
    
    # ─── Human Review ─────────────────────────────────────────────────────────
    human_feedback: Optional[str]       # Feedback from human if they reject
    approved: bool                      # Whether human approved the final script
    
    # ─── Pipeline Control ─────────────────────────────────────────────────────
    pipeline_status: str                # "researching", "drafting", "scoring", "mutating",
                                        # "visuals", "review", "publishing", "complete", "error"
    error: Optional[str]               # Error description for error_handler node
