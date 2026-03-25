import unittest
from unittest.mock import patch, MagicMock
from packages.memory.client import ZepMemoryClient
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
        client = ZepMemoryClient()
        self.assertIsNone(client._client)
        
        # Methods should return empty/default safely
        client.add_facts("session_1", [{"fact": "Test"}])
        self.assertEqual(client.search_memory("session_1", "query"), [])

    @patch('packages.memory.client.ZepMemoryClient.add_facts')
    def test_audience_model_write(self, mock_add_facts):
        # Test 2: Pakistani Audience Model Write
        feedback = FeedbackLoop()
        feedback.recalibrate_from_performance({
            "video_id": "vid123",
            "genre_id": "current_situation",
            "topic_statement": "Economy",
            "topic_resonance_score": 85.0,
            "anchor_bridge_correlation": {"bridge": 40.0}
        })
        self.assertTrue(mock_add_facts.called)
        
        args, kwargs = mock_add_facts.call_args
        facts = kwargs['facts']
        self.assertGreaterEqual(len(facts), 2)
        self.assertEqual(facts[0]['metric'], 'topic_resonance_score')
        self.assertEqual(facts[1]['metric'], 'anchor_bridge_correlation')

    @patch('packages.memory.client.ZepMemoryClient.search_memory')
    def test_topic_finder_integration(self, mock_search):
        # Test 5: Topic Finder Integration
        # Ensure it calls search_memory for semantic queries
        mock_search.return_value = [{"fact": "Historical insight 1", "score": 0.9}]
        
        agent = TopicFinderAgent()
        # We patch router.get_completion to avoid actual LLM calls
        with patch.object(agent.router, 'get_completion', return_value='{"topic_statement":"Test"}'):
            # Just test the method doesn't crash and search_memory is called
            try:
                agent.generate_candidate("Economy", "current_situation")
            except Exception:
                pass # JSON might fail parsing, but we just verify search_memory is called
                
        self.assertGreaterEqual(mock_search.call_count, 3) # Queries the audience context

    @patch('packages.memory.client.ZepMemoryClient.add_facts')
    def test_learning_log_semantic_write(self, mock_add_facts):
        # Test Learning Log dual write
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
            
        self.assertTrue(mock_add_facts.called)
        facts = mock_add_facts.call_args[1]['facts']
        self.assertEqual(len(facts), 1)
        self.assertIn("beat_baseline", facts[0])
        self.assertIn("Zone 'Zone 1' mutation", facts[0]['fact'])

    @patch('packages.memory.client.ZepMemoryClient.search_memory')
    def test_synthesis_engine_integration(self, mock_search):
        # Test 6: Learning Synthesis Engine Integration
        mock_search.return_value = [{"fact": "Semantic pattern isolated", "score": 0.9}]
        engine = SynthesisEngine()
        
        patterns = engine._detect_patterns_semantic()
        self.assertTrue(mock_search.called)
        self.assertGreaterEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["evidence"], "Semantic pattern isolated")

    @patch('packages.memory.client.ZepMemoryClient.create_session')
    @patch('packages.memory.client.add_facts')
    def test_production_cycle_session(self, mock_add_facts, mock_create_session):
        # Test 7: Production Cycle Session
        orchestrator = MasterOrchestrator()
        
        # Mock the DB so we don't need real SQLite
        orchestrator.db = MagicMock()
        orchestrator.db.get_active_cycles.return_value = []
        
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
        
        orchestrator.zep_client.add_facts = MagicMock()
        orchestrator.check_and_start_new_cycle([topic])
        
        orchestrator.zep_client.create_session.assert_called()
        orchestrator.zep_client.add_facts.assert_called()

if __name__ == '__main__':
    unittest.main()
