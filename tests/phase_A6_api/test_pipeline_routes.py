"""
test_pipeline_routes.py — Tests for the pipeline management API.

Endpoints tested:
    GET  /api/pipeline/stages         — Return pipeline stage graph definition
    POST /api/pipeline/discover       — Start LangGraph discovery graph
    POST /api/pipeline/produce/{id}   — Start LangGraph production pipeline
    POST /api/pipeline/langgraph/resume/{id}  — Resume pipeline after human review
    GET  /api/pipeline/langgraph/state/{id}   — Get checkpointed pipeline state
    GET  /api/pipeline/langgraph/preview/{id} — Preview production output

NOTE: routers/__init__.py shadows module names. Use sys.modules for patching.
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mod():
    """Get the pipeline_routes module via sys.modules."""
    return sys.modules["apps.api.routers.pipeline_routes"]


# ─── GET /api/pipeline/stages ────────────────────────────────────────────────


class TestGetStageDefinitions:
    """Tests for GET /api/pipeline/stages."""

    @pytest.mark.asyncio
    async def test_stages_returns_200(self, client):
        resp = await client.get("/api/pipeline/stages")
        assert resp.status_code == 200
        data = resp.json()
        assert "stages" in data
        assert "execution_order" in data
        assert "parallel_stages" in data

    @pytest.mark.asyncio
    async def test_stages_has_correct_number_of_stages(self, client):
        resp = await client.get("/api/pipeline/stages")
        assert len(resp.json()["stages"]) == 9

    @pytest.mark.asyncio
    async def test_stages_execution_order_matches_stages(self, client):
        resp = await client.get("/api/pipeline/stages")
        data = resp.json()
        stage_names = [s["name"] for s in data["stages"]]
        assert set(data["execution_order"]) == set(stage_names)

    @pytest.mark.asyncio
    async def test_stages_human_gates_correct(self, client):
        data = (await client.get("/api/pipeline/stages")).json()
        stages_by_name = {s["name"]: s for s in data["stages"]}
        assert stages_by_name["human_topic_approval"]["is_human_gate"] is True
        assert stages_by_name["human_review"]["is_human_gate"] is True
        assert stages_by_name["trend_analysis"]["is_human_gate"] is False

    @pytest.mark.asyncio
    async def test_stages_parallel_stages(self, client):
        data = (await client.get("/api/pipeline/stages")).json()
        assert ["seo", "visual_planning"] in data["parallel_stages"]

    @pytest.mark.asyncio
    async def test_stages_auth_enabled(self, auth_client):
        resp = await auth_client.get("/api/pipeline/stages")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_stages_unauthorized(self, unauth_client):
        resp = await unauth_client.get("/api/pipeline/stages")
        assert resp.status_code == 401


# ─── POST /api/pipeline/discover ─────────────────────────────────────────────


class TestDiscoverTopics:
    """Tests for POST /api/pipeline/discover."""

    @pytest.mark.asyncio
    async def test_discover_503_when_graph_not_initialized(self, client):
        mod = _mod()
        with patch.object(mod, "_discovery_graph", None), \
             patch.object(mod, "_init_graphs", new_callable=AsyncMock) as m_init:
            m_init.return_value = None
            resp = await client.post("/api/pipeline/discover")
            assert resp.status_code == 503
            assert "not initialized" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_discover_returns_started_status(self, client):
        mod = _mod()
        mock_graph = AsyncMock()
        with patch.object(mod, "_discovery_graph", mock_graph):
            resp = await client.post("/api/pipeline/discover?seed_hint=test+topic")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "started"
            assert "card_id" in data

    @pytest.mark.asyncio
    async def test_discover_initializes_graph_if_none(self, client):
        mod = _mod()
        mock_graph = AsyncMock()
        with patch.object(mod, "_discovery_graph", None), \
             patch.object(mod, "_init_graphs", new_callable=AsyncMock) as m_init:
            async def side_effect():
                mod._discovery_graph = mock_graph
            m_init.side_effect = side_effect
            resp = await client.post("/api/pipeline/discover")
            assert resp.status_code == 200
            m_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_discover_seed_hint_optional(self, client):
        mod = _mod()
        mock_graph = AsyncMock()
        with patch.object(mod, "_discovery_graph", mock_graph):
            resp = await client.post("/api/pipeline/discover")
            assert resp.status_code == 200


# ─── POST /api/pipeline/produce/{card_id} ────────────────────────────────────


class TestProduceContent:
    """Tests for POST /api/pipeline/produce/{card_id}."""

    @pytest.mark.asyncio
    async def test_produce_503_when_graph_not_initialized(self, client):
        mod = _mod()
        with patch.object(mod, "_production_graph", None), \
             patch.object(mod, "_init_graphs", new_callable=AsyncMock) as m_init:
            m_init.return_value = None
            resp = await client.post("/api/pipeline/produce/test-card-id")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_produce_404_when_card_not_found(self, client, _mock_supabase_client):
        mod = _mod()
        mock_graph = AsyncMock()
        mock_sb, mock_table = _mock_supabase_client
        # Configure the full mock chain: table().select().eq().execute().data = []
        mock_table.select.return_value.eq.return_value.execute.return_value.data = []
        # Patch at source AND at module level (pipeline_routes does lazy import inside function)
        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb), \
             patch.object(mod, "_production_graph", mock_graph):
            resp = await client.post("/api/pipeline/produce/nonexistent-card")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_produce_returns_started_status(self, client, _mock_supabase_client):
        mod = _mod()
        mock_graph = AsyncMock()
        mock_sb, mock_table = _mock_supabase_client
        mock_table.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "test-card", "title": "Test Topic", "topic_brief": {"title": "Test"}}
        ]
        with patch("packages.core.supabase_client.get_supabase", return_value=mock_sb), \
             patch.object(mod, "_production_graph", mock_graph):
            resp = await client.post("/api/pipeline/produce/test-card")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "started"
            assert data["card_id"] == "test-card"

    @pytest.mark.asyncio
    async def test_produce_supabase_error_returns_500(self, client):
        mod = _mod()
        mock_graph = AsyncMock()
        with patch("packages.core.supabase_client.get_supabase", side_effect=Exception("DB error")), \
             patch.object(mod, "_production_graph", mock_graph):
            resp = await client.post("/api/pipeline/produce/test-card")
            assert resp.status_code == 500


# ─── POST /api/pipeline/langgraph/resume/{card_id} ──────────────────────────


class TestResumePipeline:
    """Tests for POST /api/pipeline/langgraph/resume/{card_id}."""

    @pytest.mark.asyncio
    async def test_resume_503_when_graph_not_initialized(self, client):
        mod = _mod()
        with patch.object(mod, "_production_graph", None), \
             patch.object(mod, "_init_graphs", new_callable=AsyncMock) as m_init:
            m_init.return_value = None
            resp = await client.post(
                "/api/pipeline/langgraph/resume/test-card",
                json={"approved": True},
            )
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_resume_approved_returns_resumed(self, client):
        """Should return 'resumed' status for approved decision."""
        mod = _mod()
        mock_graph = AsyncMock()
        mock_state = MagicMock()
        mock_state.values = {
            "pipeline_status": "human_review",
            "evaluation_score": 88,
            "iteration_count": 3,
        }
        mock_graph.aget_state = AsyncMock(return_value=mock_state)

        with patch.object(mod, "_production_graph", mock_graph), \
             patch.dict("sys.modules", {"langgraph.types": MagicMock(Command=dict)}):
            resp = await client.post(
                "/api/pipeline/langgraph/resume/test-card",
                json={"approved": True},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "resumed"
            assert data["decision"]["approved"] is True

    @pytest.mark.asyncio
    async def test_resume_rejected_with_feedback(self, client):
        """Should return 'resumed' with rejection explanation."""
        mod = _mod()
        mock_graph = AsyncMock()
        mock_state = MagicMock()
        mock_state.values = {"pipeline_status": "human_review", "evaluation_score": 60, "iteration_count": 1}
        mock_graph.aget_state = AsyncMock(return_value=mock_state)

        with patch.object(mod, "_production_graph", mock_graph), \
             patch.dict("sys.modules", {"langgraph.types": MagicMock(Command=dict)}):
            resp = await client.post(
                "/api/pipeline/langgraph/resume/test-card",
                json={"approved": False, "feedback": "Needs more research"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["decision"]["approved"] is False
            assert data["decision"]["feedback"] == "Needs more research"

    @pytest.mark.asyncio
    async def test_resume_missing_body_returns_422(self, client):
        resp = await client.post(
            "/api/pipeline/langgraph/resume/test-card",
            json={"feedback": "just feedback, no approved field"},
        )
        assert resp.status_code == 422


# ─── GET /api/pipeline/langgraph/state/{card_id} ────────────────────────────


class TestGetLanggraphState:
    """Tests for GET /api/pipeline/langgraph/state/{card_id}."""

    @pytest.mark.asyncio
    async def test_state_503_when_graph_not_initialized(self, client):
        mod = _mod()
        with patch.object(mod, "_production_graph", None), \
             patch.object(mod, "_init_graphs", new_callable=AsyncMock) as m_init:
            m_init.return_value = None
            resp = await client.get("/api/pipeline/langgraph/state/test-card")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_state_returns_values(self, client):
        mod = _mod()
        mock_graph = AsyncMock()
        mock_state = MagicMock()
        mock_state.values = {"pipeline_status": "research", "iteration_count": 0, "risk_tier": "low"}
        mock_state.next = []
        mock_graph.aget_state = AsyncMock(return_value=mock_state)
        with patch.object(mod, "_production_graph", mock_graph):
            resp = await client.get("/api/pipeline/langgraph/state/test-card")
            assert resp.status_code == 200
            data = resp.json()
            assert data["card_id"] == "test-card"
            assert data["values"]["pipeline_status"] == "research"

    @pytest.mark.asyncio
    async def test_state_404_on_error(self, client):
        mod = _mod()
        mock_graph = AsyncMock()
        mock_graph.aget_state = AsyncMock(side_effect=Exception("No state found"))
        with patch.object(mod, "_production_graph", mock_graph):
            resp = await client.get("/api/pipeline/langgraph/state/test-card")
            assert resp.status_code == 404


# ─── GET /api/pipeline/langgraph/preview/{card_id} ──────────────────────────


class TestPreviewLanggraphRun:
    """Tests for GET /api/pipeline/langgraph/preview/{card_id}."""

    @pytest.mark.asyncio
    async def test_preview_503_when_graph_not_initialized(self, client):
        mod = _mod()
        with patch.object(mod, "_production_graph", None), \
             patch.object(mod, "_init_graphs", new_callable=AsyncMock) as m_init:
            m_init.return_value = None
            resp = await client.get("/api/pipeline/langgraph/preview/test-card")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_preview_returns_draft_info(self, client):
        mod = _mod()
        mock_graph = AsyncMock()
        mock_state = MagicMock()
        mock_state.values = {
            "current_draft": "Hello world, this is a script draft.",
            "best_draft": "",
            "visual_plan": "dark dramatic intro",
            "evaluation_score": 90,
            "evaluation_feedback": "Good hook, weak CTA",
            "score_categories": {"hook": 9, "cta": 5},
            "topic_brief": {"title": "Test Topic"},
            "iteration_count": 2,
            "best_score": 90,
            "pipeline_status": "human_review",
        }
        mock_graph.aget_state = AsyncMock(return_value=mock_state)
        with patch.object(mod, "_production_graph", mock_graph):
            resp = await client.get("/api/pipeline/langgraph/preview/test-card")
            assert resp.status_code == 200
            data = resp.json()
            assert data["draft"] == "Hello world, this is a script draft."
            assert data["score"] == 90
            assert data["publishable"] is True
            assert data["title"] == "Test Topic"

    @pytest.mark.asyncio
    async def test_preview_404_on_error(self, client):
        mod = _mod()
        mock_graph = AsyncMock()
        mock_graph.aget_state = AsyncMock(side_effect=Exception("No state found"))
        with patch.object(mod, "_production_graph", mock_graph):
            resp = await client.get("/api/pipeline/langgraph/preview/test-card")
            assert resp.status_code == 404


# ─── Helper function tests ───────────────────────────────────────────────────


class TestPipelineHelperFunctions:
    """Tests for pipeline_routes utility functions."""

    def test_run_to_dict_empty_run(self):
        from apps.api.routers.pipeline_routes import _run_to_dict
        result = _run_to_dict({})
        assert result["run_id"] == ""
        assert result["status"] == ""
        assert result["video_title"] == "New Pipeline Run"
        assert result["total_stages"] == 9
        assert result["completed_stages"] == 0

    def test_run_to_dict_with_stages(self):
        from apps.api.routers.pipeline_routes import _run_to_dict
        run = {
            "run_id": "test-run", "status": "running", "current_stage": "research",
            "stage_status": {"trend_analysis": "complete", "human_topic_approval": "complete", "research": "in_progress"},
        }
        result = _run_to_dict(run)
        assert result["run_id"] == "test-run"
        assert result["stages"]["trend_analysis"]["status"] == "complete"
        assert result["stages"]["research"]["status"] == "in_progress"
        assert result["completed_stages"] == 2

    def test_extract_title_from_approval(self):
        from apps.api.routers.pipeline_routes import _extract_title
        assert _extract_title({"stage_outputs": {"human_topic_approval": {"title": "My Awesome Video"}}}) == "My Awesome Video"

    def test_extract_title_from_trend(self):
        from apps.api.routers.pipeline_routes import _extract_title
        assert _extract_title({"stage_outputs": {"trend_analysis": [{"topic_statement": "Why AI Takes Over"}]}}) == "Why AI Takes Over"

    def test_extract_title_default(self):
        from apps.api.routers.pipeline_routes import _extract_title
        assert _extract_title({}) == "New Pipeline Run"

    def test_normalize_topic_candidate(self):
        from apps.api.routers.pipeline_routes import _normalize_topic_candidate
        raw = {
            "topic_statement": "AI Revolution", "big_question": "Will AI replace humans?",
            "viability_score_breakdown": {
                "total": 14,
                "gap_1": True, "gap_2": True, "gap_3": True,
                "anchor_1": "test", "anchor_2": None, "anchor_3": None, "anchor_4": None,
                "audience_1": True, "audience_2": True, "audience_3": None, "audience_4": None,
            },
        }
        result = _normalize_topic_candidate(raw)
        assert result["title"] == "AI Revolution"
        assert result["subtitle"] == "Will AI replace humans?"
        assert result["viability_total"] == 14
        assert result["viability_max"] == 17
        assert result["gap_pass"] is True
        assert result["anchor_pass"] == 1
        assert result["audience_pass"] == 2
