"""Tests for packages/memory/init_zep.py — Zep initialization."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


class TestMigrateAudienceModel:
    """Tests for migrate_audience_model()."""

    @pytest.mark.asyncio
    @patch("packages.memory.init_zep.Path")
    async def test_skips_when_file_not_exists(self, mock_path_cls):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_cls.return_value = mock_path

        mock_client = MagicMock()
        mock_client.create_session = AsyncMock()
        mock_client.add_facts = AsyncMock()

        from packages.memory.init_zep import migrate_audience_model
        await migrate_audience_model(mock_client, "audience_user")

        mock_client.create_session.assert_not_called()
        mock_client.add_facts.assert_not_called()

    @pytest.mark.asyncio
    async def test_migrates_valid_json(self, tmp_path):
        data = {
            "last_updated": "2024-01-15",
            "knowledge_baseline": {"economy": "Growing IT sector"},
            "attention_patterns": {"hooks": "Short attention span"},
            "topic_resonance_map": {"tech": 0.85},
            "genre_engagement_rankings": {"tech": 0.9},
        }
        json_file = tmp_path / "audience_model.json"
        json_file.write_text(json.dumps(data))

        with patch("packages.memory.init_zep.Path", return_value=json_file):
            mock_client = MagicMock()
            mock_client.create_session = AsyncMock()
            mock_client.add_facts = AsyncMock()

            from packages.memory.init_zep import migrate_audience_model
            await migrate_audience_model(mock_client, "audience_user")

            mock_client.create_session.assert_called_once_with(
                session_id="audience_user_session",
                user_id="audience_user",
            )
            mock_client.add_facts.assert_called_once()
            facts = mock_client.add_facts.call_args.kwargs["facts"]
            assert len(facts) == 4  # knowledge_baseline + attention + resonance + genre

    @pytest.mark.asyncio
    @patch("packages.memory.init_zep.Path")
    async def test_handles_invalid_json(self, mock_path_cls, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_cls.return_value = bad_file

        mock_client = MagicMock()
        mock_client.add_facts = AsyncMock()

        from packages.memory.init_zep import migrate_audience_model
        # Should not raise
        await migrate_audience_model(mock_client, "audience_user")
        mock_client.add_facts.assert_not_called()


class TestMigrateLearningLogs:
    """Tests for migrate_learning_logs()."""

    @pytest.mark.asyncio
    @patch("packages.memory.init_zep.Path")
    async def test_skips_when_file_not_exists(self, mock_path_cls):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_cls.return_value = mock_path

        mock_client = MagicMock()
        mock_client.add_facts = AsyncMock()

        from packages.memory.init_zep import migrate_learning_logs
        await migrate_learning_logs(mock_client, "learning_user")

        mock_client.add_facts.assert_not_called()

    @pytest.mark.asyncio
    async def test_parses_valid_jsonl(self, tmp_path):
        entries = [
            {
                "cycle_id": "c1", "mutation_zone": "anchor",
                "baseline_score": 45, "challenger_score": 62,
                "beat_baseline": True, "fixed_questions": ["q1"],
                "genre_id": "tech",
            },
            {
                "cycle_id": "c2", "mutation_zone": "hook",
                "baseline_score": 50, "challenger_score": 55,
                "beat_baseline": True,
            },
        ]
        jsonl_file = tmp_path / "learning_log.jsonl"
        with open(jsonl_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        with patch("packages.memory.init_zep.Path", return_value=jsonl_file):
            mock_client = MagicMock()
            mock_client.create_session = AsyncMock()
            mock_client.add_facts = AsyncMock()

            from packages.memory.init_zep import migrate_learning_logs
            await migrate_learning_logs(mock_client, "learning_user")

            mock_client.create_session.assert_called_once()
            facts = mock_client.add_facts.call_args.kwargs["facts"]
            assert len(facts) == 2

    @pytest.mark.asyncio
    async def test_skips_blank_lines(self, tmp_path):
        jsonl_file = tmp_path / "learning_log.jsonl"
        jsonl_file.write_text('\n\n{"cycle_id": "c1", "mutation_zone": "hook", '
                             '"baseline_score": 50, "challenger_score": 60, '
                             '"beat_baseline": true}\n\n')

        with patch("packages.memory.init_zep.Path", return_value=jsonl_file):
            mock_client = MagicMock()
            mock_client.create_session = AsyncMock()
            mock_client.add_facts = AsyncMock()

            from packages.memory.init_zep import migrate_learning_logs
            await migrate_learning_logs(mock_client, "learning_user")

            facts = mock_client.add_facts.call_args.kwargs["facts"]
            assert len(facts) == 1


class TestAsyncMain:
    """Tests for async_main()."""

    @pytest.mark.asyncio
    @patch("packages.memory.init_zep.migrate_audience_model", new_callable=AsyncMock)
    @patch("packages.memory.init_zep.migrate_learning_logs", new_callable=AsyncMock)
    @patch("packages.memory.init_zep.AsyncZepMemoryClient")
    @patch("packages.memory.init_zep.get_settings")
    async def test_calls_all_migrations(self, mock_settings, mock_client_cls,
                                         mock_migrate_learning, mock_migrate_audience):
        # Set up mock settings with required attributes
        m = MagicMock()
        m.ZEP_AUDIENCE_USER_ID = "audience_user"
        m.ZEP_LEARNING_USER_ID = "learning_user"
        m.ZEP_API_KEY = "test-key"
        mock_settings.return_value = m
        mock_client = MagicMock()
        mock_client.create_user = AsyncMock()
        mock_client_cls.return_value = mock_client

        from packages.memory.init_zep import async_main
        await async_main()

        mock_client.create_user.assert_called()
        mock_migrate_audience.assert_called_once()
        mock_migrate_learning.assert_called_once()
