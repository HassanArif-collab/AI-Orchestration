"""
Hermes Memory Architecture — The Orchestrator's Brain.

"Hermes" is the name given to the Master Orchestrator's memory and
routing intelligence. It has three memory layers that work together:

LAYER 1: Production Pattern Skills (Active Instruction Injection)
  What it is: The current "best version" of each agent's instructions,
              updated whenever the Learning Synthesis engine discovers
              a better approach.
  How it works: HermesMemoryAdapter.update_agent_skill() receives a new
                instruction from the UpdatePipeline and injects it into
                the agent's runtime context via HermesSkillPayload.
  Why it matters: This is HOW the system self-improves — not by retraining
                  the LLM, but by updating the instructions the LLM receives.

LAYER 2: Pakistani Audience Memory (User Modeling)
  What it is: Accumulated intelligence about what content patterns work
              for Pakistani YouTube audiences — genre rankings, attention
              curves, topic resonance scores.
  How it works: FeedbackLoop ingests YouTube Analytics → updates
                AudienceMemoryState → TopicFinderAgent reads it to
                calibrate which topics to suggest.
  Storage: Written to Zep Cloud (ZEP_AUDIENCE_USER_ID session) when
           ZEP_ENABLED=true. Falls back to packages/data/audience_model.json.

LAYER 3: Cross-Production Session Memory (Mutation History)
  What it is: A queryable history of which script mutations worked and
              failed across all past production cycles.
  How it works: ExperimentLoop logs every mutation result → LearningLogger
                writes to learning_log.jsonl → SynthesisEngine reads
                semantically via Zep → prevents repeating failed mutations.
  Key method: search_cross_production_memory() — called by ChallengerGenerator
              BEFORE proposing a mutation to prevent known-bad approaches.

HOW HERMES CONNECTS TO ZEP:
  Zep Cloud is the STORAGE ENGINE for Hermes memory layers 2 and 3.
  ZepMemoryClient (packages/memory/client.py) is the interface.
  Two Zep users are created at init (packages/memory/init_zep.py):
    - ZEP_AUDIENCE_USER_ID = audience intelligence (topic resonance, genre rankings)
    - ZEP_LEARNING_USER_ID = experiment results (mutation history, synthesis patterns)
  Each user has one session:
    - f"{ZEP_AUDIENCE_USER_ID}_session" — audience facts
    - f"{ZEP_LEARNING_USER_ID}_session" — learning log facts

ACTIVATION:
  Set ZEP_ENABLED=true in .env ONLY after ZEP_API_KEY is confirmed working.
  When disabled, all three layers degrade gracefully:
    - Skills: in-memory dict only (lost on restart)
    - Audience: reads from audience_model.json
    - Mutation history: reads from learning_log.jsonl

FLOW DIAGRAM:
  YouTube Analytics
       ↓ (FeedbackLoop.ingest_analytics)
  Zep Audience Session
       ↓ (TopicFinderAgent reads via ZepAudienceModelStore)
  Topic Viability Scoring

  ExperimentLoop result
       ↓ (ZepAudienceModelStore.write_experiment_result)
  Zep Learning Session
       ↓ (SynthesisEngine._detect_patterns_semantic)
  SynthesisReport + Insights
       ↓ (UpdatePipeline.process_insight)
  HermesMemoryAdapter.update_agent_skill
       ↓ (injects into agent runtime instructions)
  Better scripts next cycle
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from packages.core.logger import get_logger

logger = get_logger("HermesMemoryArchitecture")

class HermesSkillPayload(BaseModel):
    """Hermes requires JSON schemas/descriptions for active skills.
    
    This is the payload format used when injecting updated instructions
    into the Hermes runtime. Each skill represents a versioned instruction
    set for a specific agent.
    
    Fields:
      skill_name: Identifier for the skill (e.g., "researcher_instruction_set")
      description: Human-readable description of what this skill does
      active_prompt: The actual instruction text injected into the LLM context
      version_id: Unique version identifier for rollback tracking
      last_updated: ISO timestamp of when this skill was last modified
    """
    skill_name: str
    description: str
    active_prompt: str
    version_id: str
    last_updated: str

class AudienceMemoryState(BaseModel):
    """Hermes 'User Modeling' customized for the collective identity.
    
    Represents the accumulated knowledge about Pakistani YouTube audiences.
    This model is updated by FeedbackLoop after analytics ingestion and
    read by TopicFinderAgent when scoring topic candidates.
    
    Fields:
      audience_id: Fixed identifier for the Pakistani demographic
      knowledge_baseline: What the audience already knows (prevents over-explaining)
      attention_pattern_curve: Named retention pattern (e.g., "flat_drop_at_bridge")
      topic_resonance_map: Float scores per topic (higher = more resonant)
      genre_engagement_rankings: Integer rankings per genre (1 = best performing)
    """
    audience_id: str = "pakistani_youtube_demographic"
    knowledge_baseline: list[str] = Field(default_factory=list)
    attention_pattern_curve: str = "flat_drop_at_bridge"
    topic_resonance_map: dict[str, float] = Field(default_factory=dict)
    genre_engagement_rankings: dict[str, int] = Field(default_factory=dict)
    
class CrossProductionSessionGraph(BaseModel):
    """
    Subagent memory search allowing the Phase 4 Challenger Generator 
    to retrieve what mutations failed last week.
    
    This is the query result format when ChallengerGenerator asks
    "has this type of mutation historically failed?" before proposing
    a script change.
    
    Fields:
      genre: The genre being queried
      question_category: The binary question category (C, D, F, etc.)
      failed_mutations: List of mutation descriptions that failed repeatedly
    """
    genre: str
    question_category: str
    failed_mutations: list[str] = Field(default_factory=list)

class HermesMemoryAdapter:
    """
    The central adapter bridging the learning loop to agent instructions.
    
    This class is the IN-MEMORY representation of the Hermes system.
    In a production deployment, these would persist to Hermes's own
    vector store. For now, they persist via Zep Cloud (layers 2-3)
    and in-memory dict (layer 1).
    
    KEY METHODS:
      update_agent_skill(): Called by UpdatePipeline when a new instruction
                           version is activated. Stores in self.skills dict.
      update_audience_memory(): Called by FeedbackLoop after analytics ingestion.
      search_cross_production_memory(): Called by ChallengerGenerator before
                                        proposing mutations.
    
    INTEGRATION POINTS:
      - UpdatePipeline._activate_version() → update_agent_skill()
      - FeedbackLoop.ingest_analytics() → update_audience_memory()
      - ChallengerGenerator.generate_challenger() → search_cross_production_memory()
    """
    def __init__(self):
        self.skills: dict[str, HermesSkillPayload] = {}
        # In actual Hermes, we'd persist these to its vector/JSON store
        self.audience_memory = AudienceMemoryState()
        
    def update_agent_skill(self, agent_id: str, new_instruction: str, version_id: str):
        """Called by the Instruction Update Pipeline.
        
        When the SynthesisEngine discovers a better approach and the
        UpdatePipeline determines it's safe to activate, this method
        injects the new instruction into the runtime skill store.
        
        In a real Hermes deployment, this would also call the Hermes API
        to refresh its contextual scope for the affected agent.
        
        Args:
          agent_id: The agent identifier (e.g., "researcher", "writer")
          new_instruction: The updated instruction text
          version_id: Unique version ID for rollback tracking
        """
        logger.info(f"injecting_hermes_skill | agent={agent_id} version={version_id}")
        import datetime
        
        self.skills[agent_id] = HermesSkillPayload(
            skill_name=f"{agent_id}_instruction_set",
            description=f"Active directives overriding base LLM behavior for {agent_id}",
            active_prompt=new_instruction,
            version_id=version_id,
            last_updated=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        # Hermes API call would happen here to refresh its runtime contextual scope

    def update_audience_memory(self, ingestion_data: dict[str, Any]):
        """Called by the Phase 5 Analytics Ingestion component when 30-day passes.
        
        Updates the Pakistani audience model with fresh analytics data.
        This is how the system learns what content patterns resonate
        with the target demographic.
        
        Args:
          ingestion_data: Dict containing retention_curve, genre, engagement, etc.
        """
        logger.info("updating_pakistani_audience_memory")
        # Extract features like "economics hooks work better than politics"
        if "retention_curve" in ingestion_data:
            self.audience_memory.attention_pattern_curve = ingestion_data["retention_curve"]
            
        if "genre" in ingestion_data and "engagement" in ingestion_data:
            g = ingestion_data["genre"]
            self.audience_memory.genre_engagement_rankings[g] = ingestion_data["engagement"]

        # Push to Hermes representation layer

    def search_cross_production_memory(self, genre: str, category: str, proposed_mutation: str) -> bool:
        """
        Phase 4 Challenger queries this before proposing a mutation to prevent repeating mistakes.
        
        This is the PREVENTION layer of the self-improvement system. Before
        ChallengerGenerator proposes any mutation, it asks Hermes whether
        this exact type of mutation has repeatedly failed in the past.
        
        Returns:
          True if safe to proceed
          False if this mutation has a history of failure
        
        Args:
          genre: The video genre
          category: The question category being addressed
          proposed_mutation: Description of the proposed change
        """
        logger.info(f"querying_cross_production_memory | genre={genre} category={category}")
        # Mock Hermes search result
        failed_history = ["adding explicit nominals", "removing visual anchors"]
        if proposed_mutation in failed_history:
            logger.warning(f"mutation_prevented_by_hermes_memory | mutation={proposed_mutation}")
            return False
        return True
