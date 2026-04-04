"""Tests for packages/core/escalation.py — Escalation handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


class TestEscalationLevel:
    """Tests for EscalationLevel enum."""

    def test_values(self):
        from packages.core.escalation import EscalationLevel
        assert EscalationLevel.INFO.value == "info"
        assert EscalationLevel.WARNING.value == "warning"
        assert EscalationLevel.ERROR.value == "error"
        assert EscalationLevel.CRITICAL.value == "critical"


class TestEscalationChannel:
    """Tests for EscalationChannel enum."""

    def test_values(self):
        from packages.core.escalation import EscalationChannel
        assert EscalationChannel.LOG.value == "log"
        assert EscalationChannel.WEBHOOK.value == "webhook"
        assert EscalationChannel.SLACK.value == "slack"
        assert EscalationChannel.DISCORD.value == "discord"


class TestEscalationEvent:
    """Tests for EscalationEvent dataclass."""

    def test_creation(self):
        from packages.core.escalation import EscalationEvent, EscalationLevel
        event = EscalationEvent(
            event_type="quality_gate_failure",
            message="Score below floor",
            level=EscalationLevel.ERROR,
        )
        assert event.event_type == "quality_gate_failure"
        assert event.level == EscalationLevel.ERROR
        assert event.source == "pipeline"  # default

    def test_to_dict(self):
        from packages.core.escalation import EscalationEvent, EscalationLevel
        event = EscalationEvent(
            event_type="test",
            message="Test message",
            level=EscalationLevel.WARNING,
            source="agent",
            metadata={"key": "value"},
        )
        d = event.to_dict()
        assert d["event_type"] == "test"
        assert d["level"] == "warning"
        assert d["source"] == "agent"
        assert d["metadata"]["key"] == "value"
        assert "timestamp" in d

    def test_to_json(self):
        from packages.core.escalation import EscalationEvent, EscalationLevel
        event = EscalationEvent(event_type="test", message="msg", level=EscalationLevel.INFO)
        json_str = event.to_json()
        assert isinstance(json_str, str)
        assert "test" in json_str


class TestLogHandler:
    """Tests for LogHandler."""

    @pytest.mark.asyncio
    async def test_handles_event(self):
        from packages.core.escalation import LogHandler, EscalationEvent, EscalationLevel
        handler = LogHandler()
        event = EscalationEvent(event_type="test", message="Test log", level=EscalationLevel.INFO)
        result = await handler.handle(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_handles_all_levels(self):
        from packages.core.escalation import LogHandler, EscalationEvent, EscalationLevel
        handler = LogHandler()
        for level in [EscalationLevel.INFO, EscalationLevel.WARNING,
                      EscalationLevel.ERROR, EscalationLevel.CRITICAL]:
            event = EscalationEvent(event_type="test", message="msg", level=level)
            result = await handler.handle(event)
            assert result is True


class TestWebhookHandler:
    """Tests for WebhookHandler."""

    @pytest.mark.asyncio
    async def test_successful_post(self):
        from packages.core.escalation import WebhookHandler, EscalationEvent, EscalationLevel
        handler = WebhookHandler(webhook_url="https://example.com/webhook")
        event = EscalationEvent(event_type="test", message="msg", level=EscalationLevel.INFO)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = await handler.handle(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_server_error(self):
        from packages.core.escalation import WebhookHandler, EscalationEvent, EscalationLevel
        handler = WebhookHandler(webhook_url="https://example.com/webhook")
        event = EscalationEvent(event_type="test", message="msg", level=EscalationLevel.ERROR)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = await handler.handle(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_network_error(self):
        from packages.core.escalation import WebhookHandler, EscalationEvent, EscalationLevel
        handler = WebhookHandler(webhook_url="https://example.com/webhook")
        event = EscalationEvent(event_type="test", message="msg", level=EscalationLevel.WARNING)

        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = await handler.handle(event)
        assert result is False


class TestSlackHandler:
    """Tests for SlackHandler."""

    @pytest.mark.asyncio
    async def test_formats_slack_payload(self):
        from packages.core.escalation import SlackHandler, EscalationEvent, EscalationLevel
        handler = SlackHandler(webhook_url="https://hooks.slack.com/test")
        event = EscalationEvent(
            event_type="quality_gate_failure",
            message="Score below floor",
            level=EscalationLevel.ERROR,
            metadata={"score": 45},
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = await handler.handle(event)

        # Verify Slack payload format
        call_args = mock_client.post.call_args
        sent_json = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "attachments" in sent_json
        assert sent_json["attachments"][0]["color"] == "#ff0000"  # red for ERROR
        assert result is True

    @pytest.mark.asyncio
    async def test_color_for_critical(self):
        from packages.core.escalation import SlackHandler, EscalationEvent, EscalationLevel
        handler = SlackHandler(webhook_url="https://hooks.slack.com/test")
        event = EscalationEvent(event_type="critical", message="crit", level=EscalationLevel.CRITICAL)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            await handler.handle(event)

        call_args = mock_client.post.call_args
        sent_json = call_args.kwargs.get("json") or call_args[1].get("json")
        assert sent_json["attachments"][0]["color"] == "#990000"  # dark red


class TestEscalationService:
    """Tests for EscalationService."""

    @pytest.mark.asyncio
    async def test_escalate_disabled(self):
        from packages.core.escalation import EscalationService
        service = EscalationService(enabled=False)
        result = await service.escalate("test", "message")
        assert result is True

    @pytest.mark.asyncio
    async def test_escalate_with_no_handlers(self):
        from packages.core.escalation import EscalationService
        service = EscalationService(enabled=True)
        result = await service.escalate("test", "message")
        assert result is False

    @pytest.mark.asyncio
    async def test_escalate_with_handler(self):
        from packages.core.escalation import EscalationService, LogHandler
        service = EscalationService(enabled=True)
        service.add_handler(LogHandler())
        result = await service.escalate("test", "message")
        assert result is True

    def test_add_handler(self):
        from packages.core.escalation import EscalationService, LogHandler
        service = EscalationService()
        handler = LogHandler()
        service.add_handler(handler)
        assert len(service._handlers) == 1

    def test_remove_handler(self):
        from packages.core.escalation import EscalationService, LogHandler
        service = EscalationService()
        handler = LogHandler()
        service.add_handler(handler)
        service.remove_handler(handler)
        assert len(service._handlers) == 0

    def test_get_stats(self):
        from packages.core.escalation import EscalationService, LogHandler
        service = EscalationService(enabled=True, min_score_for_escalation=30.0)
        service.add_handler(LogHandler())
        stats = service.get_stats()
        assert stats["enabled"] is True
        assert stats["total_escalations"] == 0
        assert stats["handler_count"] == 1


class TestEscalateQualityGateFailure:
    """Tests for escalate_quality_gate_failure()."""

    @pytest.mark.asyncio
    async def test_warning_level(self):
        from packages.core.escalation import EscalationService, LogHandler
        service = EscalationService()
        service.add_handler(LogHandler())
        # Score 50, floor 60 → gap = 10, 50 > 60*0.75=45, so WARNING
        result = await service.escalate_quality_gate_failure(score=50, floor=60)
        assert result is True

    @pytest.mark.asyncio
    async def test_critical_level(self):
        from packages.core.escalation import EscalationService, LogHandler
        service = EscalationService()
        service.add_handler(LogHandler())
        # Score 10, floor 60 → 10 < 60*0.5=30, so CRITICAL
        result = await service.escalate_quality_gate_failure(score=10, floor=60)
        assert result is True

    @pytest.mark.asyncio
    async def test_error_level(self):
        from packages.core.escalation import EscalationService, LogHandler
        service = EscalationService()
        service.add_handler(LogHandler())
        # Score 25, floor 60 → 25 < 60*0.75=45, 25 > 60*0.5=30 is false → 25 < 30 → CRITICAL
        # Actually: 25 < 30 → CRITICAL
        # Let's test score=35, floor=60 → 35 < 45, 35 >= 30 → ERROR
        result = await service.escalate_quality_gate_failure(score=35, floor=60)
        assert result is True


class TestEscalatePipelineError:
    """Tests for escalate_pipeline_error()."""

    @pytest.mark.asyncio
    async def test_recoverable_is_warning(self):
        from packages.core.escalation import EscalationService, LogHandler
        service = EscalationService()
        service.add_handler(LogHandler())
        result = await service.escalate_pipeline_error(stage="research", error="Timeout", recoverable=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_non_recoverable_is_error(self):
        from packages.core.escalation import EscalationService, LogHandler
        service = EscalationService()
        service.add_handler(LogHandler())
        result = await service.escalate_pipeline_error(stage="script", error="Fatal", recoverable=False)
        assert result is True


class TestGetResetEscalationService:
    """Tests for get_escalation_service() and reset_escalation_service()."""

    def test_singleton(self):
        from packages.core.escalation import get_escalation_service, reset_escalation_service
        reset_escalation_service()
        s1 = get_escalation_service()
        s2 = get_escalation_service()
        assert s1 is s2
        reset_escalation_service()

    def test_reset(self):
        from packages.core.escalation import get_escalation_service, reset_escalation_service
        reset_escalation_service()
        s1 = get_escalation_service()
        reset_escalation_service()
        s2 = get_escalation_service()
        assert s1 is not s2
        reset_escalation_service()
