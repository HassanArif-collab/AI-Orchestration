"""
test_kanban.py — Tests for Kanban Dashboard functionality.

Tests cover:
- Kanban API endpoints (CRUD operations)
- KanbanCallbackHandler agent integration
- TopicFinderAgent Kanban integration
- SSE event broadcasting
"""

import asyncio
import json
import pytest
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ─── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    # Initialize schema
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kanban_tasks (
            id TEXT PRIMARY KEY,
            parent_id TEXT,
            title TEXT NOT NULL,
            stage INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'idle',
            color TEXT NOT NULL,
            content TEXT DEFAULT '',
            research TEXT DEFAULT '',
            script TEXT DEFAULT '',
            visual_cues TEXT DEFAULT '',
            notion_url TEXT DEFAULT '',
            thoughts TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def kanban_routes(temp_db):
    """Create Kanban routes with test database."""
    from apps.api.routers import kanban_routes
    # Patch the database path
    kanban_routes._KANBAN_DB_PATH = temp_db
    return kanban_routes


# ─── Kanban API Tests ────────────────────────────────────────────────────────────

class TestKanbanAPI:
    """Tests for Kanban API endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_task(self, kanban_routes):
        """Test creating a new Kanban task."""
        task_data = kanban_routes.KanbanTaskCreate(
            title="Test Topic",
            stage=1
        )
        
        result = await kanban_routes.create_task(task_data)
        
        assert result["id"] is not None
        assert result["title"] == "Test Topic"
        assert result["stage"] == 1
        assert result["status"] == "idle"
        assert result["color"] is not None
    
    @pytest.mark.asyncio
    async def test_create_task_with_parent(self, kanban_routes):
        """Test creating a child task inherits color from parent."""
        # Create parent task
        parent_data = kanban_routes.KanbanTaskCreate(
            title="Parent Topic",
            stage=1,
            color="#ff0000"
        )
        parent = await kanban_routes.create_task(parent_data)
        
        # Create child task without color
        child_data = kanban_routes.KanbanTaskCreate(
            title="Child Topic",
            stage=2,
            parent_id=parent["id"]
        )
        child = await kanban_routes.create_task(child_data)
        
        # Child should inherit parent's color
        assert child["color"] == "#ff0000"
        assert child["parent_id"] == parent["id"]
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, kanban_routes):
        """Test listing Kanban tasks."""
        # Create some tasks
        for i in range(3):
            await kanban_routes.create_task(
                kanban_routes.KanbanTaskCreate(title=f"Task {i}", stage=1)
            )
        
        result = await kanban_routes.list_tasks()
        
        assert len(result["tasks"]) >= 3
    
    @pytest.mark.asyncio
    async def test_update_task(self, kanban_routes):
        """Test updating a Kanban task."""
        # Create task
        task = await kanban_routes.create_task(
            kanban_routes.KanbanTaskCreate(title="Original Title", stage=1)
        )
        
        # Update task
        update_data = kanban_routes.KanbanTaskUpdate(
            title="Updated Title",
            stage=2,
            status="thinking"
        )
        result = await kanban_routes.update_task(task["id"], update_data)
        
        assert result["title"] == "Updated Title"
        assert result["stage"] == 2
        assert result["status"] == "thinking"
    
    @pytest.mark.asyncio
    async def test_delete_task(self, kanban_routes):
        """Test deleting a Kanban task."""
        # Create task
        task = await kanban_routes.create_task(
            kanban_routes.KanbanTaskCreate(title="Task to Delete", stage=1)
        )
        
        # Delete task
        result = await kanban_routes.delete_task(task["id"])
        
        assert result["success"] is True
        
        # Verify task is gone
        with pytest.raises(Exception):  # Should raise 404
            await kanban_routes.get_task(task["id"])
    
    @pytest.mark.asyncio
    async def test_report_thought_event(self, kanban_routes):
        """Test reporting a thought event."""
        # Create task
        task = await kanban_routes.create_task(
            kanban_routes.KanbanTaskCreate(title="Test Task", stage=1)
        )
        
        # Report thought
        event = kanban_routes.KanbanEvent(
            task_id=task["id"],
            event_type="thought",
            data={"content": "Analyzing topic viability..."}
        )
        result = await kanban_routes.report_event(event)
        
        assert result["success"] is True
        
        # Verify thought was stored
        updated = await kanban_routes.get_task(task["id"])
        thoughts = json.loads(updated["thoughts"])
        assert len(thoughts) == 1
        assert thoughts[0]["content"] == "Analyzing topic viability..."
    
    @pytest.mark.asyncio
    async def test_report_stage_change_event(self, kanban_routes):
        """Test reporting a stage change event."""
        # Create task
        task = await kanban_routes.create_task(
            kanban_routes.KanbanTaskCreate(title="Test Task", stage=1)
        )
        
        # Report stage change
        event = kanban_routes.KanbanEvent(
            task_id=task["id"],
            event_type="stage_change",
            data={"stage": 3}
        )
        result = await kanban_routes.report_event(event)
        
        assert result["success"] is True
        
        # Verify stage was updated
        updated = await kanban_routes.get_task(task["id"])
        assert updated["stage"] == 3
    
    @pytest.mark.asyncio
    async def test_report_artifact_event(self, kanban_routes):
        """Test reporting an artifact event."""
        # Create task
        task = await kanban_routes.create_task(
            kanban_routes.KanbanTaskCreate(title="Test Task", stage=3)
        )
        
        # Report artifact
        event = kanban_routes.KanbanEvent(
            task_id=task["id"],
            event_type="artifact",
            data={"key": "research", "value": "Research content here..."}
        )
        result = await kanban_routes.report_event(event)
        
        assert result["success"] is True
        
        # Verify artifact was stored
        updated = await kanban_routes.get_task(task["id"])
        assert updated["research"] == "Research content here..."


# ─── KanbanCallbackHandler Tests ───────────────────────────────────────────────────

class TestKanbanCallbackHandler:
    """Tests for KanbanCallbackHandler."""
    
    @pytest.mark.asyncio
    async def test_on_thought(self):
        """Test reporting a thought."""
        from packages.agents.kanban_callback import KanbanCallbackHandler
        
        handler = KanbanCallbackHandler(task_id="test-task-id", base_url="http://test")
        
        with patch.object(handler, '_post_event', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = True
            
            await handler._post_event("thought", {"content": "Test thought"})
            
            mock_post.assert_called_once_with(
                "thought",
                {"content": "Test thought"}
            )
    
    @pytest.mark.asyncio
    async def test_on_stage_change(self):
        """Test reporting a stage change."""
        from packages.agents.kanban_callback import KanbanCallbackHandler
        
        handler = KanbanCallbackHandler(task_id="test-task-id")
        
        with patch.object(handler, '_post_event', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = True
            
            result = await handler.on_stage_change(3)
            
            assert result is True
            mock_post.assert_called_once_with("stage_change", {"stage": 3})
    
    @pytest.mark.asyncio
    async def test_on_stage_change_invalid(self):
        """Test reporting invalid stage is rejected."""
        from packages.agents.kanban_callback import KanbanCallbackHandler
        
        handler = KanbanCallbackHandler(task_id="test-task-id")
        
        result = await handler.on_stage_change(7)  # Invalid stage
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_on_status_change(self):
        """Test reporting a status change."""
        from packages.agents.kanban_callback import KanbanCallbackHandler
        
        handler = KanbanCallbackHandler(task_id="test-task-id")
        
        with patch.object(handler, '_post_event', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = True
            
            result = await handler.on_status_change("thinking")
            
            assert result is True
            mock_post.assert_called_once_with("status_change", {"status": "thinking"})
    
    @pytest.mark.asyncio
    async def test_on_artifact(self):
        """Test reporting an artifact."""
        from packages.agents.kanban_callback import KanbanCallbackHandler
        
        handler = KanbanCallbackHandler(task_id="test-task-id")
        
        with patch.object(handler, '_post_event', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = True
            
            result = await handler.on_artifact("research", "Research content")
            
            assert result is True
            mock_post.assert_called_once_with(
                "artifact",
                {"key": "research", "value": "Research content"}
            )


# ─── TopicFinderAgent Integration Tests ────────────────────────────────────────────

class TestTopicFinderIntegration:
    """Tests for TopicFinderAgent Kanban integration."""
    
    @pytest.mark.asyncio
    async def test_topic_finder_initializes_with_kanban_id(self):
        """Test TopicFinderAgent accepts kanban_task_id."""
        from packages.content_factory.topic_finder.finder import TopicFinderAgent
        
        agent = TopicFinderAgent(kanban_task_id="test-kanban-id")
        
        assert agent.kanban_task_id == "test-kanban-id"
        assert agent._kanban_callback is None  # Not initialized until needed
    
    @pytest.mark.asyncio
    async def test_topic_finder_without_kanban_id(self):
        """Test TopicFinderAgent works without kanban_task_id."""
        from packages.content_factory.topic_finder.finder import TopicFinderAgent
        
        agent = TopicFinderAgent()
        
        assert agent.kanban_task_id is None
        assert agent._kanban_callback is None
    
    @pytest.mark.asyncio
    async def test_report_thought_helper(self):
        """Test _report_thought helper method."""
        from packages.content_factory.topic_finder.finder import TopicFinderAgent
        
        agent = TopicFinderAgent(kanban_task_id="test-id")
        agent._kanban_callback = MagicMock()
        agent._kanban_callback.on_thought = AsyncMock(return_value=True)
        
        await agent._report_thought("Test thought")
        
        agent._kanban_callback.on_thought.assert_called_once_with("Test thought")
    
    @pytest.mark.asyncio
    async def test_report_thought_no_callback(self):
        """Test _report_thought does nothing without callback."""
        from packages.content_factory.topic_finder.finder import TopicFinderAgent
        
        agent = TopicFinderAgent()  # No kanban_task_id
        
        # Should not raise any error
        await agent._report_thought("Test thought")


# ─── Stage Mapping Tests ───────────────────────────────────────────────────────────

class TestStageMapping:
    """Tests for pipeline stage to Kanban stage mapping."""
    
    def test_stage_mapping_exists(self):
        """Test that stage mapping is defined."""
        from packages.agents.kanban_callback import PIPELINE_TO_KANBAN_STAGE
        
        assert len(PIPELINE_TO_KANBAN_STAGE) == 9
        
        # Verify all values are valid Kanban stages (1-6)
        for stage in PIPELINE_TO_KANBAN_STAGE.values():
            assert 1 <= stage <= 6
    
    def test_get_kanban_stage(self):
        """Test get_kanban_stage helper function."""
        from packages.agents.kanban_callback import get_kanban_stage
        
        assert get_kanban_stage("research") == 3
        assert get_kanban_stage("script_writing") == 4
        assert get_kanban_stage("unknown_stage") == 1  # Default


# ─── Stats Endpoint Tests ───────────────────────────────────────────────────────────

class TestStatsEndpoint:
    """Tests for the stats endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_stats(self, kanban_routes):
        """Test getting Kanban statistics."""
        # Create tasks in different stages
        for stage in range(1, 7):
            await kanban_routes.create_task(
                kanban_routes.KanbanTaskCreate(title=f"Task Stage {stage}", stage=stage)
            )
        
        stats = await kanban_routes.get_stats()
        
        assert stats["total_tasks"] >= 6
        assert "by_stage" in stats
        assert "by_status" in stats
        
        # Check that each stage has at least 1 task
        for stage in range(1, 7):
            assert stats["by_stage"][stage] >= 1


# ─── Topic Finder API Tests ─────────────────────────────────────────────────────────

class TestTopicFinderAPI:
    """Tests for the Topic Finder API endpoint."""
    
    @pytest.mark.asyncio
    async def test_trigger_topic_finder(self, kanban_routes):
        """Test triggering the Topic Finder agent."""
        request_data = kanban_routes.TopicFinderRequest(
            seed_query="AI in healthcare",
            genre_id="tech"
        )
        
        # Mock the background task
        with patch('asyncio.create_task'):
            result = await kanban_routes.trigger_topic_finder(request_data)
        
        assert result["id"] is not None
        assert result["status"] == "thinking"
        assert "Topic finder started" in result["message"]
    
    @pytest.mark.asyncio
    async def test_topic_finder_creates_task(self, kanban_routes):
        """Test that triggering Topic Finder creates a Kanban task."""
        request_data = kanban_routes.TopicFinderRequest(
            seed_query="Test query",
            genre_id="default"
        )
        
        with patch('asyncio.create_task'):
            result = await kanban_routes.trigger_topic_finder(request_data)
        
        # Verify task was created
        task = await kanban_routes.get_task(result["id"])
        assert task is not None
        assert task["stage"] == 1
        assert task["status"] == "thinking"


# ─── Title Extraction Tests (Task 7.1) ─────────────────────────────────────────────

class TestTitleExtraction:
    """Tests for title extraction from pipeline runs in Kanban view."""
    
    def test_extract_title_from_normalized_approval(self):
        """Test that _run_to_kanban_dict extracts title from normalized approval.
        
        When a user approves a topic, the selection contains the NORMALIZED topic
        candidate which has 'title' (mapped from 'topic_statement'), not the raw
        'topic_statement' field.
        
        This test verifies that the Kanban title extraction correctly reads the
        'title' field from the normalized approval selection.
        """
        from apps.api.routers.kanban_routes import _run_to_kanban_dict
        
        # Create a mock run with normalized approval output
        # This simulates what happens after user approves a topic
        mock_run = MagicMock()
        mock_run.to_dict.return_value = {
            "run_id": "test-run-123",
            "current_stage": "research",
            "status": "running",
            "stage_outputs": {
                "human_topic_approval": {
                    # This is the NORMALIZED topic candidate (from _normalize_topic_candidate)
                    # It has 'title' field, NOT 'topic_statement'
                    "title": "Why Pakistan's AI Policy Matters",
                    "subtitle": "What if the real bottleneck isn't technology?",
                    "gap_type": "Practical Gap",
                    "viability_total": 15,
                    "viability_max": 17,
                    "gap_pass": True,
                    "anchor_pass": 3,
                    "audience_pass": 3,
                }
            },
            "stage_status": {
                "trend_analysis": "complete",
                "human_topic_approval": "complete",
                "research": "running"
            },
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z"
        }
        
        result = _run_to_kanban_dict(mock_run)
        
        # The title should be extracted from the 'title' field, not 'topic_statement'
        assert result["title"] == "Why Pakistan's AI Policy Matters", \
            f"Expected 'Why Pakistan's AI Policy Matters', got '{result['title']}'"
    
    def test_extract_title_fallback_to_topic_statement(self):
        """Test that _run_to_kanban_dict falls back to topic_statement if title missing."""
        from apps.api.routers.kanban_routes import _run_to_kanban_dict
        
        # Create a mock run with raw (non-normalized) approval output
        mock_run = MagicMock()
        mock_run.to_dict.return_value = {
            "run_id": "test-run-456",
            "current_stage": "research",
            "status": "running",
            "stage_outputs": {
                "human_topic_approval": {
                    # Raw topic candidate has 'topic_statement', not 'title'
                    "topic_statement": "Raw Topic Statement",
                    "big_question": "What if...?",
                }
            },
            "stage_status": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z"
        }
        
        result = _run_to_kanban_dict(mock_run)
        
        # Should fall back to topic_statement
        assert result["title"] == "Raw Topic Statement", \
            f"Expected fallback to 'Raw Topic Statement', got '{result['title']}'"
    
    def test_extract_title_from_trend_analysis(self):
        """Test that _run_to_kanban_dict extracts title from trend_analysis if no approval."""
        from apps.api.routers.kanban_routes import _run_to_kanban_dict
        
        # Create a mock run with no approval, but with trend_analysis
        mock_run = MagicMock()
        mock_run.to_dict.return_value = {
            "run_id": "test-run-789",
            "current_stage": "human_topic_approval",
            "status": "waiting_human",
            "stage_outputs": {
                "trend_analysis": [
                    {
                        "title": "First Trend Topic",
                        "topic_statement": "First Trend Statement",
                        "viability_total": 10
                    }
                ]
            },
            "stage_status": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z"
        }
        
        result = _run_to_kanban_dict(mock_run)
        
        # Should use trend_analysis first item's title
        assert result["title"] == "First Trend Topic", \
            f"Expected 'First Trend Topic', got '{result['title']}'"


# ─── Run Tests ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
