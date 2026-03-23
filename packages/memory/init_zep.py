import json
import logging
from pathlib import Path
from packages.core.config import get_settings
from packages.memory.client import ZepMemoryClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InitZep")

def migrate_audience_model(client: ZepMemoryClient, audience_user_id: str):
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
        client.create_session(session_id=session_id, user_id=audience_user_id)
        client.add_facts(session_id=session_id, facts=facts)
        logger.info(f"Successfully migrated {len(facts)} facts to audience model.")
    except Exception as e:
        logger.error(f"Migration error for audience model: {e}")

def migrate_learning_logs(client: ZepMemoryClient, learning_user_id: str):
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
        client.create_session(session_id=session_id, user_id=learning_user_id)
        
        # client.add_facts already batches sizes of 50 internally
        client.add_facts(session_id=session_id, facts=facts)
        logger.info(f"Successfully migrated {len(facts)} learning logs.")
    except Exception as e:
        logger.error(f"Migration error for learning logs: {e}")

def main():
    settings = get_settings()
    audience_user_id = settings.ZEP_AUDIENCE_USER_ID
    learning_user_id = settings.ZEP_LEARNING_USER_ID
    
    if not settings.ZEP_API_KEY:
        logger.warning("No ZEP_API_KEY found. Operating in degraded mode. Migration will be a no-op.")

    client = ZepMemoryClient()
    
    # Init users
    logger.info("Initializing Zep Users...")
    client.create_user(user_id=audience_user_id, metadata={"purpose": "Pakistani Audience Model evolution"})
    client.create_user(user_id=learning_user_id, metadata={"purpose": "Cross-Cycle Pattern Synthesis from Learning Logs"})
    
    # Migrate data
    migrate_audience_model(client, audience_user_id)
    migrate_learning_logs(client, learning_user_id)

    logger.info("Initialization and Migration Complete.")

if __name__ == "__main__":
    main()
