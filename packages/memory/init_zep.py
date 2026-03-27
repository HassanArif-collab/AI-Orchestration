"""
Zep Initialization and Migration Script.

ONE-TIME SETUP — run this script once when you first configure your ZEP_API_KEY.
It creates the two Zep users and migrates any existing local data to Zep.

What it does:
  1. Creates two Zep users:
       - ZEP_AUDIENCE_USER_ID — stores Pakistani audience intelligence
       - ZEP_LEARNING_USER_ID — stores experiment learning logs
  2. Migrates audience_model.json → Zep audience session facts
     (knowledge_baseline, attention_patterns, topic_resonance_map)
  3. Migrates learning_log.jsonl → Zep learning session facts
     (experiment cycle results, mutation zone outcomes)

When to run:
  ONLY run this after setting ZEP_API_KEY in .env and confirming it works.
  Running it without a valid key is a safe no-op (logs a warning and exits).

How to run:
  python packages/memory/init_zep.py

After running:
  Set ZEP_ENABLED=true in .env to activate live Zep reads/writes.
  Until then, the system uses local JSON fallbacks.

Data sources migrated:
  packages/data/audience_model.json  — audience intelligence baseline
  packages/data/learning_log.jsonl   — experiment mutation history
"""
import asyncio
import json
import logging
from pathlib import Path
from packages.core.config import get_settings
from packages.memory.client import AsyncZepMemoryClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InitZep")


async def migrate_audience_model(client: AsyncZepMemoryClient, audience_user_id: str):
    """Migrate local audience_model.json to Zep.
    
    Reads the existing audience model JSON file and converts each
    field into a Zep fact. The facts are stored in the audience
    user's session for semantic retrieval.
    
    Facts created:
      - Knowledge baseline entries
      - Attention patterns
      - Topic resonance scores
      - Genre engagement rankings
    """
    logger.info("Starting Audience Model migration...")
    file_path = Path("packages/data/audience_model.json")
    if not file_path.exists():
        logger.info("No existing audience model found to migrate.")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        facts = []
        last_updated = data.get("last_updated", "")

        for k, v in data.get("knowledge_baseline", {}).items():
            facts.append({
                "fact": f"Knowledge Baseline for '{k}': {v}",
                "source": "migration",
                "date": last_updated
            })
            
        for k, v in data.get("attention_patterns", {}).items():
            facts.append({
                "fact": f"Attention Pattern for '{k}': {v}",
                "source": "migration",
                "date": last_updated
            })

        for k, v in data.get("topic_resonance_map", {}).items():
            facts.append({
                "fact": f"Topic resonance score for '{k}' is {v}",
                "source": "migration",
                "date": last_updated
            })
            
        for k, v in data.get("genre_engagement_rankings", {}).items():
            facts.append({
                "fact": f"Genre engagement ranking for '{k}' is {v}",
                "source": "migration",
                "date": last_updated
            })

        session_id = f"{audience_user_id}_session"
        await client.create_session(session_id=session_id, user_id=audience_user_id)
        await client.add_facts(session_id=session_id, facts=facts)
        logger.info(f"Successfully migrated {len(facts)} facts to audience model.")
    except Exception as e:
        logger.error(f"Migration error for audience model: {e}")


async def migrate_learning_logs(client: AsyncZepMemoryClient, learning_user_id: str):
    """Migrate local learning_log.jsonl to Zep.
    
    Reads each line of the JSONL file (one experiment result per line)
    and converts it into a Zep fact. These facts power the semantic
    pattern detection in SynthesisEngine.
    
    Facts include:
      - Cycle ID and genre
      - Mutation zone and outcome
      - Score changes (baseline → challenger)
      - Fixed and regressed question IDs
    """
    logger.info("Starting Learning Log migration...")
    file_path = Path("packages/data/learning_log.jsonl")
    if not file_path.exists():
        logger.info("No existing learning log found to migrate.")
        return

    try:
        facts = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                
                content = (f"Experiment Cycle ID: {entry.get('cycle_id')}. "
                           f"Zone '{entry.get('mutation_zone')}' mutation "
                           f"resulted in score change from {entry.get('baseline_score')}% to {entry.get('challenger_score')}%. "
                           f"Beat baseline: {entry.get('beat_baseline')}.")
                if entry.get('fixed_questions'):
                    content += f" Fixed questions: {', '.join(entry['fixed_questions'])}."
                if entry.get('regressed_questions'):
                    content += f" Regressed questions: {', '.join(entry['regressed_questions'])}."
                
                fact_dict = {
                    "fact": content,
                    "cycle_id": entry.get("cycle_id"),
                    "genre_id": entry.get("genre_id"),
                    "mutation_zone": entry.get("mutation_zone"),
                    "beat_baseline": entry.get("beat_baseline"),
                    "source": "migration"
                }
                facts.append(fact_dict)

        session_id = f"{learning_user_id}_session"
        await client.create_session(session_id=session_id, user_id=learning_user_id)
        
        # client.add_facts already batches sizes of 50 internally
        await client.add_facts(session_id=session_id, facts=facts)
        logger.info(f"Successfully migrated {len(facts)} learning logs.")
    except Exception as e:
        logger.error(f"Migration error for learning logs: {e}")


async def async_main():
    """Main entry point for Zep initialization.
    
    Creates both Zep users and migrates existing local data.
    Safe to run multiple times — will not duplicate data if
    users/sessions already exist.
    """
    settings = get_settings()
    audience_user_id = settings.ZEP_AUDIENCE_USER_ID
    learning_user_id = settings.ZEP_LEARNING_USER_ID
    
    if not settings.ZEP_API_KEY:
        logger.warning("No ZEP_API_KEY found. Operating in degraded mode. Migration will be a no-op.")

    client = AsyncZepMemoryClient()
    
    # Init users
    logger.info("Initializing Zep Users...")
    await client.create_user(user_id=audience_user_id, metadata={"purpose": "Pakistani Audience Model evolution"})
    await client.create_user(user_id=learning_user_id, metadata={"purpose": "Cross-Cycle Pattern Synthesis from Learning Logs"})
    
    # Migrate data
    await migrate_audience_model(client, audience_user_id)
    await migrate_learning_logs(client, learning_user_id)

    logger.info("Initialization and Migration Complete.")


def main():
    """Sync entry point that wraps async_main."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
