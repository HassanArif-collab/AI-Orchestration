"""
Mode B Pipeline — Original Pakistani Investigative Content.

Takes a TopicBrief and produces an original DualColumnScript using three
CrewAI agents working in sequence with iterative self-correction rounds.

Agents: Researcher → Visual Director → Writer (defined in agents.py)
Workflow: RoundBasedProductionWorkflow in workflow.py
Entry point: workflow.py → run_production_workflow(idea, ...)

Genres supported: history, current_situation, tech_systems, comparison,
                  islamic_history, south_asian_history
"""

# packages/content_factory/production — Phase 3 Core Production System
