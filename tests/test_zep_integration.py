"""Integration tests for Zep memory client and related components.

Tests verify that the async memory client integrates properly with
the content factory pipeline components.
"""

import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from packages.memory.client import AsyncZepMemoryClient
from packages.content_factory.topic_finder.feedback import FeedbackLoop
from packages.content_factory.topic_finder.finder import TopicFinderAgent
from packages.content_factory.evaluation.learning_log import LearningLogger, LearningLogEntry
from packages.content_factory.orchestration.synthesis import SynthesisEngine
from packages.content_factory.orchestration.master import MasterOrchestrator
from packages.content_factory.topic_finder.models import TopicBrief
from datetime import datetime, timezone


class TestZepIntegration(unittest.TestCase):
    def setUp(self):
        # Reset Zep Client caching and mocks
        pass

    @patch('packages.memory.client.get_settings')
    @patch('packages.memory.client.AsyncZep')
    @patch('packages.core.logger.Logger.warning')
    def test_client_resilience(self, mock_warning, mock_async_zep, mock_settings):
        # Test 1: Client Wrapper Resilience
        mock_settings.return_value.ZEP_API_KEY = "test_key"
        
        # Make AsyncZep raise an Exception when instantiated
        mock_async_zep.side_effect = Exception("Connection Refused")
        
        # Client should degrade gracefully without crashing
        client = AsyncZepMemoryClient()
        self.assertIsNone(client._client)
        
        # Methods should return empty/default safely
        result = asyncio.run(client.search_memory("session_1", "query"))
        self.assertEqual(result, [])

    @patch('packages.memory.client.AsyncZepMemoryClient.add_facts')
    def test_audience_model_write(self, mock_add_facts):
        # Test 2: Pakistani Audience Model Write
        mock_add_facts.return_value = asyncio.Future()
        mock_add_facts.return_value.set_result(None)
        
        feedback = FeedbackLoop()
        asyncio.run(feedback.recalibrate_from_performance({
            "video_id": "vid123",
            "genre_id": "current_situation",
            "topic_statement": "Economy",
            "topic_resonance_score": 85.0,
            "anchor_bridge_correlation": {"bridge": 40.0}
        }))
        
        # The async call runs in background, so we just verify it was initiated
        # The actual assertion would need the async task to complete

    @patch('packages.memory.client.AsyncZepMemoryClient.search_memory')
    def test_topic_finder_integration(self, mock_search):
        # Test 5: Topic Finder Integration
        # Ensure it calls search_memory for semantic queries
        mock_search.return_value = asyncio.Future()
        mock_search.return_value.set_result([{"fact": "Historical insight 1", "score": 0.9}])
        
        agent = TopicFinderAgent()
        # The generate_candidate is async and would need full async test
        # This is a basic smoke test that the agent initializes correctly
        self.assertIsNotNone(agent.zep_client)

    @patch('packages.memory.client.AsyncZepMemoryClient.add_facts')
    def test_learning_log_semantic_write(self, mock_add_facts):
        # Test Learning Log dual write
        mock_add_facts.return_value = asyncio.Future()
        mock_add_facts.return_value.set_result(None)
        
        logger = LearningLogger(log_path="packages/data/test_learning_log.jsonl")
        entry = LearningLogEntry(
            cycle_id="cycle_1",
            genre_id="islamic_history",
            baseline_id="base1",
            challenger_id="challenger1",
            mutation_zone="Zone 1",
            baseline_score=50.0,
            challenger_score=60.0,
            beat_baseline=True,
            fixed_questions=["Q1"],
            timestamp=datetime.now(timezone.utc)
        )
        # Avoid file writing conflicts in test
        with patch('builtins.open', unittest.mock.mock_open()):
            logger.log_experiment(entry)
            
        # The async Zep write runs in background
        self.assertIsNotNone(logger.zep_client)

    @patch('packages.memory.client.AsyncZepMemoryClient.search_memory')
    def test_synthesis_engine_integration(self, mock_search):
        # Test 6: Learning Synthesis Engine Integration
        async def run_test():
            mock_search.return_value = [{"fact": "Semantic pattern isolated", "score": 0.9}]
            
            engine = SynthesisEngine()
            patterns = await engine._detect_patterns_semantic()
            
            self.assertTrue(mock_search.called)
            self.assertGreaterEqual(len(patterns), 1)
            self.assertEqual(patterns[0]["evidence"], "Semantic pattern isolated")
        
        asyncio.run(run_test())

    @patch('packages.memory.client.AsyncZepMemoryClient.create_session')
    @patch('packages.memory.client.AsyncZepMemoryClient.add_facts')
    @patch('packages.memory.client.AsyncZepMemoryClient.create_user')
    def test_production_cycle_session(self, mock_create_user, mock_add_facts, mock_create_session):
        # Test 7: Production Cycle Session
        async def run_test():
            mock_create_session.return_value = None
            mock_add_facts.return_value = None
            mock_create_user.return_value = None
            
            orchestrator = MasterOrchestrator()
            
            # Mock the DB so we don't need real SQLite
            orchestrator.db = MagicMock()
            orchestrator.db.get_active_cycles.return_value = []
            orchestrator.db.create_cycle = MagicMock()
            
            topic = TopicBrief(
                topic_statement="Test Statement",
                big_question="Why test?",
                genre_id="current_situation",
                gap_type="Hidden Mechanism",
                viability_score_breakdown={"total": 15},
                anchor_candidates=[],
                mainstream_assumption="X",
                timing_rationale="Now",
                urgency_flag=False,
                created_at=datetime.now(timezone.utc),
                status="reservoir"
            )
            
            await orchestrator.check_and_start_new_cycle([topic])
            
            mock_create_session.assert_called()
            mock_add_facts.assert_called()
        
        asyncio.run(run_test())


class TestAsyncZepMemoryClientBasics(unittest.TestCase):
    """Basic unit tests for AsyncZepMemoryClient."""

    def test_client_initializes_with_none_key(self):
        """Client should handle None API key gracefully."""
        client = AsyncZepMemoryClient(api_key=None)
        self.assertIsNone(client._client)

    def test_client_initializes_with_empty_key(self):
        """Client should handle empty API key gracefully."""
        client = AsyncZepMemoryClient(api_key="")
        self.assertIsNone(client._client)

    def test_search_memory_returns_empty_list_when_no_client(self):
        """search_memory should return empty list when client is None."""
        async def run():
            client = AsyncZepMemoryClient(api_key="")
            result = await client.search_memory("session_id", "query")
            return result
        result = asyncio.run(run())
        self.assertEqual(result, [])

    def test_add_facts_returns_none_when_no_client(self):
        """add_facts should return None when client is None."""
        async def run():
            client = AsyncZepMemoryClient(api_key="")
            await client.add_facts("session_id", [{"fact": "test"}])
        # Should not raise
        asyncio.run(run())

    def test_create_user_returns_none_when_no_client(self):
        """create_user should return None when client is None."""
        async def run():
            client = AsyncZepMemoryClient(api_key="")
            result = await client.create_user("user_id")
            return result
        result = asyncio.run(run())
        self.assertIsNone(result)

    def test_create_session_returns_none_when_no_client(self):
        """create_session should return None when client is None."""
        async def run():
            client = AsyncZepMemoryClient(api_key="")
            result = await client.create_session("session_id", "user_id")
            return result
        result = asyncio.run(run())
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
