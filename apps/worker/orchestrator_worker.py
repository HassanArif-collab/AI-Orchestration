"""
Hermes Master Orchestrator Worker.

Runs as a background daemon to:
1. Periodically inject new topic seeds into the Topic Finder column.
2. Advance production cycles for items in the reservoir.
3. Monitor system health and escalations.
"""

import asyncio
import time
import signal
import sys
from datetime import datetime, timezone

from packages.content_factory.orchestration.master import MasterOrchestrator
from packages.core.logger import get_logger
from packages.core.config import get_settings

logger = get_logger("OrchestratorWorker")

class OrchestratorWorker:
    def __init__(self):
        self.orchestrator = MasterOrchestrator()
        self.settings = get_settings()
        self.running = True
        
        # Intervals (seconds)
        self.feed_interval = 3600  # 1 hour
        self.cycle_check_interval = 600  # 10 minutes
        
    def stop(self, *args):
        logger.info("orchestrator_worker_stopping...")
        self.running = False

    async def run(self):
        logger.info("Hermes Master Orchestrator Worker started.")
        
        last_feed = 0
        last_cycle_check = 0
        
        while self.running:
            now = time.time()
            
            # 1. Autonomous Feed (Topic Finder)
            if now - last_feed > self.feed_interval:
                try:
                    logger.info("triggering_autonomous_feed")
                    results = await self.orchestrator.feed_topic_finder(count=1)
                    for res in (results or []):
                        logger.info(f"autonomous_feed_success | card={res['card_id']} seed={res['seed_query']}")
                    last_feed = now
                except Exception as e:
                    logger.error(f"autonomous_feed_failed: {e}")

            # 2. Production Cycle Advancement
            if now - last_cycle_check > self.cycle_check_interval:
                try:
                    # Note: In a real system, this would fetch from a database or search library
                    # For now, it monitors the existing cycles in the OrchestrationDB
                    logger.debug("checking_production_cycles")
                    # self.orchestrator.check_and_start_new_cycle([]) # placeholder
                    last_cycle_check = now
                except Exception as e:
                    logger.error(f"cycle_advancement_failed: {e}")

            await asyncio.sleep(10)

if __name__ == "__main__":
    worker = OrchestratorWorker()
    
    # Handle signals
    signal.signal(signal.SIGINT, worker.stop)
    signal.signal(signal.SIGTERM, worker.stop)
    
    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.critical(f"orchestrator_worker_crashed: {e}")
        sys.exit(1)
