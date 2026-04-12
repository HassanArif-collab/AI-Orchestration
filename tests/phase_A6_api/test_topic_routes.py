"""
test_topic_routes.py — Tests for the topic reservoir management API.

Endpoints tested:
    GET    /api/topics/reservoir          — Get topics from reservoir
    GET    /api/topics/reservoir/{id}     — Get single topic by ID
    POST   /api/topics/approve            — Approve a topic
    POST   /api/topics/reject             — Reject a topic
    POST   /api/topics/custom             — Submit custom topic
    POST   /api/topics/custom-script      — Submit custom script
    POST   /api/topics/rescan             — Trigger topic rescan
    GET    /api/topics/stats              — Get topic statistics
    DELETE /api/topics/reservoir/{id}     — Delete a topic

NOTE: routers/__init__.py shadows module names with router objects.
Use sys.modules to access the actual module for patching.
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock


def _mod():
    """Get the topic_routes module via sys.modules."""
    return sys.modules["apps.api.routers.topic_routes"]


SAMPLE_TOPICS = [
    {
        "id": "topic-1",
        "topic_statement": "Why AI is revolutionizing education",
        "big_question": "How will AI change learning?",
        "genre_id": "current_situation",
        "status": "reservoir",
        "is_tier_1": True,
        "source": "daily_scan",
        "created_at": "2025-01-15T10:00:00Z",
    },
    {
        "id": "topic-2",
        "topic_statement": "The hidden cost of fast fashion",
        "big_question": "Why cheap clothes are expensive",
        "genre_id": "current_situation",
        "status": "approved",
        "is_tier_1": False,
        "source": "user_input",
        "created_at": "2025-01-14T10:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def _mock_background_tasks():
    """Mock background task functions to prevent file I/O."""
    with patch("apps.api.background_tasks.start_research_for_topic", new_callable=AsyncMock), \
         patch("apps.api.background_tasks.evaluate_script", new_callable=AsyncMock), \
         patch("apps.api.background_tasks.run_daily_scan", new_callable=AsyncMock):
        yield


@pytest.fixture()
def temp_reservoir(tmp_path):
    """Patch RESERVOIR_FILE to a temp directory with sample data."""
    mod = _mod()
    original = mod.RESERVOIR_FILE

    topics_file = tmp_path / "topics.json"
    topics_file.write_text(json.dumps(SAMPLE_TOPICS))
    mod.RESERVOIR_FILE = topics_file

    yield topics_file

    mod.RESERVOIR_FILE = original


class TestGetReservoirTopics:
    """Tests for GET /api/topics/reservoir."""

    @pytest.mark.asyncio
    async def test_reservoir_default_filter(self, client, temp_reservoir):
        """Should return topics with 'reservoir' status by default."""
        resp = await client.get("/api/topics/reservoir")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["topics"][0]["id"] == "topic-1"

    @pytest.mark.asyncio
    async def test_reservoir_all_status(self, client, temp_reservoir):
        """Should return all topics when status=all."""
        resp = await client.get("/api/topics/reservoir?status=all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_reservoir_genre_filter(self, client, temp_reservoir):
        """Should filter by genre_id."""
        resp = await client.get("/api/topics/reservoir?genre=current_situation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_reservoir_by_status_counts(self, client, temp_reservoir):
        """Should include by_status breakdown."""
        resp = await client.get("/api/topics/reservoir")
        assert resp.status_code == 200
        data = resp.json()
        assert "reservoir" in data["by_status"]
        assert "approved" in data["by_status"]
        assert data["by_status"]["reservoir"] == 1

    @pytest.mark.asyncio
    async def test_reservoir_include_scores(self, client, temp_reservoir):
        """Should include scores when requested."""
        resp = await client.get("/api/topics/reservoir?include_scores=true")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_reservoir_limit(self, client, temp_reservoir):
        """Should respect limit parameter."""
        resp = await client.get("/api/topics/reservoir?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["topics"]) <= 1


class TestGetTopic:
    """Tests for GET /api/topics/reservoir/{topic_id}."""

    @pytest.mark.asyncio
    async def test_get_topic_found(self, client, temp_reservoir):
        """Should return a topic by ID."""
        resp = await client.get("/api/topics/reservoir/topic-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "topic-1"

    @pytest.mark.asyncio
    async def test_get_topic_404(self, client, temp_reservoir):
        """Should return 404 for nonexistent topic."""
        resp = await client.get("/api/topics/reservoir/nonexistent")
        assert resp.status_code == 404


class TestApproveTopic:
    """Tests for POST /api/topics/approve."""

    @pytest.mark.asyncio
    async def test_approve_success(self, client, temp_reservoir):
        """Should approve a topic."""
        resp = await client.post("/api/topics/approve", json={
            "topic_id": "topic-1",
            "notes": "Good topic",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["topic_id"] == "topic-1"

    @pytest.mark.asyncio
    async def test_approve_404(self, client, temp_reservoir):
        """Should return 404 for nonexistent topic."""
        resp = await client.post("/api/topics/approve", json={
            "topic_id": "nonexistent",
        })
        assert resp.status_code == 404


class TestRejectTopic:
    """Tests for POST /api/topics/reject."""

    @pytest.mark.asyncio
    async def test_reject_success(self, client, temp_reservoir):
        """Should reject a topic."""
        resp = await client.post("/api/topics/reject", json={
            "topic_id": "topic-1",
            "reason": "Not relevant",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reject_404(self, client, temp_reservoir):
        """Should return 404 for nonexistent topic."""
        resp = await client.post("/api/topics/reject", json={
            "topic_id": "nonexistent",
        })
        assert resp.status_code == 404


class TestSubmitCustomTopic:
    """Tests for POST /api/topics/custom."""

    @pytest.mark.asyncio
    async def test_custom_topic_created(self, client, temp_reservoir):
        """Should create a new custom topic."""
        resp = await client.post("/api/topics/custom", json={
            "topic_statement": "My custom topic idea",
            "genre_id": "future_impact",
            "big_question": "What if...",
            "notes": "Research this",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert "topic_id" in data
        assert data["topic_id"].startswith("custom_")

    @pytest.mark.asyncio
    async def test_custom_topic_persisted(self, client, temp_reservoir):
        """Should persist the custom topic to file."""
        resp = await client.post("/api/topics/custom", json={
            "topic_statement": "Persistent topic",
        })
        assert resp.status_code == 200

        # Verify it's in the reservoir
        resp2 = await client.get("/api/topics/reservoir?status=all")
        data = resp2.json()
        found = [t for t in data["topics"] if t["topic_statement"] == "Persistent topic"]
        assert len(found) == 1


class TestSubmitCustomScript:
    """Tests for POST /api/topics/custom-script."""

    @pytest.mark.asyncio
    async def test_custom_script_created(self, client, temp_reservoir):
        """Should create a new custom script."""
        resp = await client.post("/api/topics/custom-script", json={
            "title": "My Script Title",
            "genre_id": "current_situation",
            "script_content": "Here is the script content...",
            "notes": "Initial draft",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert "topic_id" in data
        assert "script_id" in data


class TestTriggerRescan:
    """Tests for POST /api/topics/rescan."""

    @pytest.mark.asyncio
    async def test_rescan_started(self, client, temp_reservoir):
        """Should start a topic rescan."""
        resp = await client.post("/api/topics/rescan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"

    @pytest.mark.asyncio
    async def test_rescan_with_genres(self, client, temp_reservoir):
        """Should accept genre filter."""
        resp = await client.post("/api/topics/rescan?genres=current_situation,future_impact")
        assert resp.status_code == 200


class TestGetTopicStats:
    """Tests for GET /api/topics/stats."""

    @pytest.mark.asyncio
    async def test_stats_returns_data(self, client, temp_reservoir):
        """Should return topic statistics."""
        resp = await client.get("/api/topics/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert "by_status" in data
        assert "by_genre" in data
        assert "by_source" in data
        assert data["tier_1_count"] == 1

    @pytest.mark.asyncio
    async def test_stats_empty_reservoir(self, client, tmp_path):
        """Should return zeros for empty reservoir."""
        mod = _mod()
        original = mod.RESERVOIR_FILE
        empty_file = tmp_path / "empty_topics.json"
        empty_file.write_text("[]")
        mod.RESERVOIR_FILE = empty_file

        resp = await client.get("/api/topics/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

        mod.RESERVOIR_FILE = original


class TestDeleteTopic:
    """Tests for DELETE /api/topics/reservoir/{topic_id}."""

    @pytest.mark.asyncio
    async def test_delete_success(self, client, temp_reservoir):
        """Should delete a topic."""
        resp = await client.delete("/api/topics/reservoir/topic-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"
        assert data["topic_id"] == "topic-1"

        # Verify it's gone
        resp2 = await client.get("/api/topics/reservoir/topic-1")
        assert resp2.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_404(self, client, temp_reservoir):
        """Should return 404 for nonexistent topic."""
        resp = await client.delete("/api/topics/reservoir/nonexistent")
        assert resp.status_code == 404
