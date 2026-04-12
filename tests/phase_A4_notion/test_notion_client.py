"""
test_notion_client.py — Unit tests for NotionScriptClient and color/emoji utilities.

All Notion API calls are mocked — no real network traffic.
Tests use pytest-asyncio with asyncio_mode = "auto" (configured in pyproject.toml).

Critical implementation notes:
- NotionScriptClient.__init__ calls get_settings() for default api_key/database_id.
  The autouse conftest fixture patches get_settings() so tests use clean defaults.
- create_script_page / update_script_page are async but call the synchronous
  notion_client SDK. Exceptions from the SDK are caught *inside* the method's
  try/except, so the @retry_with_backoff decorator does NOT retry them.
  We mock asyncio.sleep as a safety net anyway.
- For error cases (auth, rate-limit), the SDK method is mocked to raise the
  appropriate exception, which the method's except block converts to an
  OperationResult.fail.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from packages.core.operation_result import OperationResult, ErrorSeverity


# ---------------------------------------------------------------------------
# Helper: build a NotionScriptClient without running __init__
# ---------------------------------------------------------------------------

def _make_client(
    api_key: str | None = None,
    database_id: str | None = None,
    _client: MagicMock | None = None,
) -> "NotionScriptClient":
    """Build a NotionScriptClient bypassing __init__ (no get_settings / imports).

    This is the recommended approach for most tests — it avoids the
    notion_client import and get_settings() call inside __init__.
    """
    from packages.integrations.notion.client import NotionScriptClient
    client = NotionScriptClient.__new__(NotionScriptClient)
    client.api_key = api_key
    client.database_id = database_id
    client._client = _client
    return client


def _sample_script_data(entries: list[dict] | None = None) -> dict:
    """Return a minimal script_data dict suitable for create_script_page."""
    if entries is None:
        entries = [
            {
                "section_type": "Intro",
                "narration": "Welcome to the video.",
                "visual_cue": "Host appears on screen",
                "visual_type": "talking_head",
            },
            {
                "section_type": "Main Content",
                "narration": "Here is the core idea.",
                "visual_cue": "Animated diagram",
                "visual_type": "animation",
            },
        ]
    return {"entries": entries}


# =========================================================================
# TestNotionClientInit
# =========================================================================

class TestNotionClientInit:
    """Tests for NotionScriptClient.__init__."""

    def test_init_with_api_key(self, _mock_get_settings):
        """When api_key is provided, Client(auth=api_key) is called."""
        from packages.integrations.notion.client import NotionScriptClient

        mock_client_instance = MagicMock()
        mock_notion_module = MagicMock()
        mock_notion_module.Client.return_value = mock_client_instance

        with patch.dict("sys.modules", {"notion_client": mock_notion_module}):
            nc = NotionScriptClient(api_key="secret_test", database_id="db_123")

        mock_notion_module.Client.assert_called_once_with(auth="secret_test")
        assert nc._client is mock_client_instance
        assert nc.api_key == "secret_test"
        assert nc.database_id == "db_123"

    def test_init_without_api_key(self, _mock_get_settings):
        """When no api_key is provided and settings has no key, _client stays None."""
        from packages.integrations.notion.client import NotionScriptClient

        nc = NotionScriptClient(api_key="", database_id="db_123")
        assert nc._client is None

    def test_init_import_error(self, _mock_get_settings):
        """When notion_client is not installed (ImportError), _client stays None."""
        import sys
        import importlib
        from packages.integrations.notion.client import NotionScriptClient

        # Save original state and remove notion_client from sys.modules if present
        saved_modules = {k: sys.modules.pop(k, None) for k in list(sys.modules) if k == "notion_client" or k.startswith("notion_client.")}

        # Patch builtins.__import__ to raise ImportError for notion_client
        import builtins
        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if name == "notion_client" or name.startswith("notion_client."):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        try:
            builtins.__import__ = failing_import
            # Also need to invalidate any cached import of the client module
            # so that the lazy `from notion_client import Client` inside __init__ hits our mock
            nc = NotionScriptClient(api_key="secret_test")
        finally:
            builtins.__import__ = original_import
            # Restore saved modules
            for k, v in saved_modules.items():
                if v is not None:
                    sys.modules[k] = v
                elif k in sys.modules:
                    del sys.modules[k]

        # Client should be None because the import failed
        assert nc._client is None


# =========================================================================
# TestCheckClient
# =========================================================================

class TestCheckClient:
    """Tests for NotionScriptClient._check_client."""

    def test_check_client_available(self):
        """When _client is set, returns OperationResult.ok(None)."""
        client = _make_client(api_key="secret", _client=MagicMock())
        result = client._check_client()
        assert result.success is True
        assert result.data is None

    def test_check_client_unavailable(self):
        """When _client is None, returns fail with NOTION_NOT_CONFIGURED."""
        client = _make_client(api_key=None, _client=None)
        result = client._check_client()
        assert result.success is False
        assert result.error_code == "NOTION_NOT_CONFIGURED"
        assert result.severity == ErrorSeverity.CRITICAL


# =========================================================================
# TestCreateScriptPage
# =========================================================================

class TestCreateScriptPage:
    """Tests for NotionScriptClient.create_script_page (async)."""

    async def test_create_script_page_success(self):
        """Creates page and returns OperationResult.ok(page_url)."""
        mock_api = MagicMock()
        mock_api.pages.create.return_value = {
            "id": "abc",
            "url": "https://notion.so/abc",
        }
        client = _make_client(
            api_key="secret_test",
            database_id="test_db_id",
            _client=mock_api,
        )

        with patch("packages.integrations.notion.client.queue_for_retry") as mock_dlq:
            result = await client.create_script_page(
                title="Test Video",
                script_data=_sample_script_data(),
            )

        assert result.success is True
        assert result.data == "https://notion.so/abc"
        mock_api.pages.create.assert_called_once()
        call_kwargs = mock_api.pages.create.call_args[1]
        assert call_kwargs["parent"]["database_id"] == "test_db_id"
        assert "Video name" in call_kwargs["properties"]
        # Verify children were built (heading + narration + callout per entry = 6 blocks)
        assert len(call_kwargs["children"]) == 6
        mock_dlq.assert_not_called()

    async def test_create_script_page_no_client(self):
        """When _client is None, returns fail with NOTION_NOT_CONFIGURED."""
        client = _make_client(api_key=None, _client=None, database_id="db_1")

        result = await client.create_script_page(
            title="Test",
            script_data=_sample_script_data(),
        )

        assert result.success is False
        assert result.error_code == "NOTION_NOT_CONFIGURED"

    async def test_create_script_page_no_database_id(self):
        """When database_id is empty, returns fail with NOTION_NOT_CONFIGURED."""
        mock_api = MagicMock()
        client = _make_client(
            api_key="secret_test",
            database_id="",
            _client=mock_api,
        )

        result = await client.create_script_page(
            title="Test",
            script_data=_sample_script_data(),
        )

        assert result.success is False
        assert result.error_code == "NOTION_NOT_CONFIGURED"

    async def test_create_script_page_blocks_limit(self):
        """Notion allows max 100 blocks — children must be truncated to 100."""
        mock_api = MagicMock()
        mock_api.pages.create.return_value = {"id": "x", "url": "https://notion.so/x"}

        # Build 40 entries, each producing 3 blocks (heading + narration + callout) = 120 blocks
        entries = [
            {
                "section_type": f"Section {i}",
                "narration": f"Narration text {i}",
                "visual_cue": f"Visual cue {i}",
                "visual_type": "talking_head",
            }
            for i in range(40)
        ]

        client = _make_client(
            api_key="secret_test",
            database_id="test_db_id",
            _client=mock_api,
        )

        with patch("packages.integrations.notion.client.queue_for_retry"):
            result = await client.create_script_page(
                title="Blocks Test",
                script_data={"entries": entries},
            )

        assert result.success is True
        call_kwargs = mock_api.pages.create.call_args[1]
        # 40 entries × 3 blocks = 120, truncated to 100
        assert len(call_kwargs["children"]) == 100

    async def test_create_script_page_auth_error(self):
        """When exception contains 'authentication', error_code is NOTION_AUTH_FAILED and retryable=False."""
        mock_api = MagicMock()
        mock_api.pages.create.side_effect = Exception("authentication failed for this request")

        client = _make_client(
            api_key="secret_test",
            database_id="test_db_id",
            _client=mock_api,
        )

        with patch("packages.integrations.notion.client.queue_for_retry") as mock_dlq:
            with patch("packages.core.retry.asyncio.sleep"):
                result = await client.create_script_page(
                    title="Auth Fail Test",
                    script_data=_sample_script_data(),
                    run_id="run_42",
                )

        assert result.success is False
        assert result.error_code == "NOTION_AUTH_FAILED"
        assert result.retryable is False
        assert "authentication" in result.user_message.lower()
        mock_dlq.assert_called_once()
        call_kwargs = mock_dlq.call_args[1]
        assert call_kwargs["operation"] == "notion_publish"
        assert call_kwargs["error_code"] == "NOTION_AUTH_FAILED"
        assert call_kwargs["run_id"] == "run_42"

    async def test_create_script_page_rate_limit(self):
        """When exception contains 'rate' or '429', error_code is NOTION_RATE_LIMIT and severity=WARNING."""
        mock_api = MagicMock()
        mock_api.pages.create.side_effect = Exception("rate limit exceeded: 429 Too Many Requests")

        client = _make_client(
            api_key="secret_test",
            database_id="test_db_id",
            _client=mock_api,
        )

        with patch("packages.integrations.notion.client.queue_for_retry") as mock_dlq:
            with patch("packages.core.retry.asyncio.sleep"):
                result = await client.create_script_page(
                    title="Rate Limit Test",
                    script_data=_sample_script_data(),
                )

        assert result.success is False
        assert result.error_code == "NOTION_RATE_LIMIT"
        assert result.severity == ErrorSeverity.WARNING
        assert result.retryable is True
        mock_dlq.assert_called_once()
        call_kwargs = mock_dlq.call_args[1]
        assert call_kwargs["error_code"] == "NOTION_RATE_LIMIT"
        assert call_kwargs["severity"] == "warning"


# =========================================================================
# TestUpdateScriptPage
# =========================================================================

class TestUpdateScriptPage:
    """Tests for NotionScriptClient.update_script_page (async)."""

    async def test_update_script_page_success(self):
        """Appends blocks and returns OperationResult.ok(None)."""
        mock_api = MagicMock()
        mock_api.blocks.children.append.return_value = {"results": []}

        client = _make_client(
            api_key="secret_test",
            database_id="test_db_id",
            _client=mock_api,
        )

        sections = [
            {
                "section_type": "New Section",
                "narration": "New narration.",
                "visual_cue": "New visual",
                "visual_type": "broll",
            },
        ]

        with patch("packages.integrations.notion.client.queue_for_retry"):
            result = await client.update_script_page(
                page_id="page_123",
                sections=sections,
                run_id="run_99",
            )

        assert result.success is True
        mock_api.blocks.children.append.assert_called_once()
        call_kwargs = mock_api.blocks.children.append.call_args[1]
        assert call_kwargs["block_id"] == "page_123"
        # heading + narration + callout = 3 children
        assert len(call_kwargs["children"]) == 3

    async def test_update_script_page_no_client(self):
        """When _client is None, returns fail with NOTION_NOT_CONFIGURED."""
        client = _make_client(api_key=None, _client=None, database_id="db_1")

        result = await client.update_script_page(
            page_id="page_123",
            sections=[{"section_type": "X", "narration": "Y"}],
        )

        assert result.success is False
        assert result.error_code == "NOTION_NOT_CONFIGURED"


# =========================================================================
# TestGetScript
# =========================================================================

class TestGetScript:
    """Tests for NotionScriptClient.get_script (async)."""

    async def test_get_script_success(self):
        """Retrieves page and blocks, returns OperationResult with title, sections, url."""
        mock_api = MagicMock()
        mock_api.pages.retrieve.return_value = {
            "id": "page_abc",
            "url": "https://notion.so/page_abc",
            "properties": {
                "title": {
                    "type": "title",
                    "title": [{"text": {"content": "My Great Video"}}],
                },
            },
        }
        mock_api.blocks.children.list.return_value = {
            "results": [
                {
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "Intro"}}],
                    },
                },
                {
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": "Welcome to the show."}}],
                    },
                },
                {
                    "type": "callout",
                    "callout": {
                        "rich_text": [{"text": {"content": "Host smiles at camera"}}],
                        "color": "red",
                    },
                },
            ],
        }

        client = _make_client(
            api_key="secret_test",
            database_id="test_db_id",
            _client=mock_api,
        )

        result = await client.get_script(page_id="page_abc")

        assert result.success is True
        data = result.data
        assert data["title"] == "My Great Video"
        assert data["url"] == "https://notion.so/page_abc"
        assert len(data["sections"]) == 1
        section = data["sections"][0]
        assert section["section_type"] == "Intro"
        assert section["narration"] == "Welcome to the show."
        assert section["visual_cue"] == "Host smiles at camera"
        assert section["visual_type"] == "talking_head"  # inferred from "red" color

    async def test_get_script_no_client(self):
        """When _client is None, returns fail."""
        client = _make_client(api_key=None, _client=None, database_id="db_1")

        result = await client.get_script(page_id="page_abc")

        assert result.success is False
        assert result.error_code == "NOTION_NOT_CONFIGURED"


# =========================================================================
# TestNotionColors
# =========================================================================

class TestNotionColors:
    """Tests for get_color and get_emoji in colors.py."""

    def test_get_color_known_type(self):
        """Returns correct color for known visual types."""
        from packages.integrations.notion.colors import get_color

        assert get_color("talking_head") == "red"
        assert get_color("animation") == "blue"
        assert get_color("broll") == "green"
        assert get_color("screen_recording") == "yellow"
        assert get_color("data_viz") == "purple"
        assert get_color("shader_bg") == "gray"

    def test_get_color_unknown_type(self):
        """Returns 'default' for unknown type."""
        from packages.integrations.notion.colors import get_color

        assert get_color("nonexistent_type") == "default"
        assert get_color("") == "default"

    def test_get_emoji_known_type(self):
        """Returns correct emoji for known types."""
        from packages.integrations.notion.colors import get_emoji

        assert get_emoji("talking_head") == "🔴"
        assert get_emoji("animation") == "🔵"
        assert get_emoji("broll") == "🟢"
        assert get_emoji("screen_recording") == "🟡"
        assert get_emoji("data_viz") == "🟣"
        assert get_emoji("shader_bg") == "⚫"

    def test_get_emoji_unknown_type(self):
        """Returns '⬜' for unknown type."""
        from packages.integrations.notion.colors import get_emoji

        assert get_emoji("nonexistent_type") == "⬜"
        assert get_emoji("") == "⬜"
