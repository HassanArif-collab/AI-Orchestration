"""Tests for NotionScriptClient and color mappings.

Tests verify graceful degradation - all methods return None/empty values
when Notion API is unavailable, and no exceptions are raised.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestNotionColors:
    """Tests for Notion color mappings."""

    def test_get_color_talking_head(self):
        """get_color should return 'red' for 'talking_head'."""
        from packages.integrations.notion.colors import get_color

        assert get_color("talking_head") == "red"

    def test_get_color_animation(self):
        """get_color should return 'blue' for 'animation'."""
        from packages.integrations.notion.colors import get_color

        assert get_color("animation") == "blue"

    def test_get_color_broll(self):
        """get_color should return 'green' for 'broll'."""
        from packages.integrations.notion.colors import get_color

        assert get_color("broll") == "green"

    def test_get_color_screen_recording(self):
        """get_color should return 'yellow' for 'screen_recording'."""
        from packages.integrations.notion.colors import get_color

        assert get_color("screen_recording") == "yellow"

    def test_get_color_data_viz(self):
        """get_color should return 'purple' for 'data_viz'."""
        from packages.integrations.notion.colors import get_color

        assert get_color("data_viz") == "purple"

    def test_get_color_shader_bg(self):
        """get_color should return 'gray' for 'shader_bg'."""
        from packages.integrations.notion.colors import get_color

        assert get_color("shader_bg") == "gray"

    def test_get_color_unknown(self):
        """get_color should return 'default' for unknown types."""
        from packages.integrations.notion.colors import get_color

        assert get_color("unknown_type") == "default"

    def test_get_emoji_talking_head(self):
        """get_emoji should return red circle for 'talking_head'."""
        from packages.integrations.notion.colors import get_emoji

        assert get_emoji("talking_head") == "🔴"

    def test_get_emoji_unknown(self):
        """get_emoji should return white square for unknown types."""
        from packages.integrations.notion.colors import get_emoji

        assert get_emoji("unknown_type") == "⬜"


class TestNotionScriptClient:
    """Tests for NotionScriptClient."""

    def test_no_exception_when_api_key_empty(self):
        """NotionScriptClient should not crash when api_key is empty."""
        from packages.integrations.notion.client import NotionScriptClient

        # Should not raise any exception
        client = NotionScriptClient(api_key="")
        assert client._client is None

    def test_no_exception_when_api_key_none(self):
        """NotionScriptClient should not crash when api_key is None."""
        from packages.integrations.notion.client import NotionScriptClient

        # Should not raise any exception
        client = NotionScriptClient(api_key=None)
        assert client._client is None

    def test_create_script_page_returns_none_when_client_none(self):
        """create_script_page should return None when client is None."""
        from packages.integrations.notion.client import NotionScriptClient

        client = NotionScriptClient(api_key="")
        result = client.create_script_page(
            title="Test Script",
            sections=[
                {
                    "section_type": "Intro",
                    "narration": "Welcome to the video",
                    "visual_cue": "Talking head shot",
                    "visual_type": "talking_head",
                }
            ],
        )
        assert result is None

    def test_create_script_page_returns_none_when_no_database_id(self):
        """create_script_page should return None when database_id is not set."""
        from packages.integrations.notion.client import NotionScriptClient

        client = NotionScriptClient(api_key="fake_key", database_id="")
        result = client.create_script_page(
            title="Test Script",
            sections=[{"section_type": "Intro", "narration": "Test"}],
        )
        assert result is None

    def test_update_script_page_doesnt_crash_when_client_none(self):
        """update_script_page should not crash when client is None."""
        from packages.integrations.notion.client import NotionScriptClient

        client = NotionScriptClient(api_key="")
        # Should not raise
        client.update_script_page(
            page_id="test_page_id",
            sections=[{"section_type": "Intro", "narration": "Test"}],
        )

    def test_get_script_returns_empty_dict_when_client_none(self):
        """get_script should return {} when client is None."""
        from packages.integrations.notion.client import NotionScriptClient

        client = NotionScriptClient(api_key="")
        result = client.get_script("test_page_id")
        assert result == {}

    def test_create_script_page_handles_api_error(self):
        """create_script_page should return None on API error."""
        from packages.integrations.notion.client import NotionScriptClient

        client = NotionScriptClient(api_key="fake_key", database_id="fake_db_id")

        # Mock the client to raise an exception
        client._client = MagicMock()
        client._client.pages.create.side_effect = Exception("API Error")

        result = client.create_script_page(
            title="Test Script",
            sections=[{"section_type": "Intro", "narration": "Test"}],
        )
        assert result is None

    def test_update_script_page_handles_api_error(self):
        """update_script_page should not crash on API error."""
        from packages.integrations.notion.client import NotionScriptClient

        client = NotionScriptClient(api_key="fake_key")

        # Mock the client to raise an exception
        client._client = MagicMock()
        client._client.blocks.children.append.side_effect = Exception("API Error")

        # Should not raise
        client.update_script_page(
            page_id="test_page_id",
            sections=[{"section_type": "Intro", "narration": "Test"}],
        )

    def test_get_script_handles_api_error(self):
        """get_script should return {} on API error."""
        from packages.integrations.notion.client import NotionScriptClient

        client = NotionScriptClient(api_key="fake_key")

        # Mock the client to raise an exception
        client._client = MagicMock()
        client._client.pages.retrieve.side_effect = Exception("API Error")

        result = client.get_script("test_page_id")
        assert result == {}

    def test_create_script_page_with_mocked_client(self):
        """create_script_page should return URL when successful."""
        from packages.integrations.notion.client import NotionScriptClient

        client = NotionScriptClient(api_key="fake_key", database_id="fake_db_id")

        # Mock the client
        client._client = MagicMock()
        client._client.pages.create.return_value = {
            "id": "page_id_123",
            "url": "https://notion.so/page_id_123",
        }

        result = client.create_script_page(
            title="Test Script",
            sections=[
                {
                    "section_type": "Intro",
                    "narration": "Welcome to the video",
                    "visual_cue": "Talking head shot",
                    "visual_type": "talking_head",
                },
                {
                    "section_type": "Main",
                    "narration": "Main content here",
                    "visual_cue": "Animation showing the concept",
                    "visual_type": "animation",
                },
            ],
        )

        assert result == "https://notion.so/page_id_123"
        # Verify the create was called with correct structure
        client._client.pages.create.assert_called_once()
        call_args = client._client.pages.create.call_args
        assert call_args.kwargs["parent"]["database_id"] == "fake_db_id"

    def test_get_script_with_mocked_client(self):
        """get_script should return parsed content when successful."""
        from packages.integrations.notion.client import NotionScriptClient

        client = NotionScriptClient(api_key="fake_key")

        # Mock the client
        client._client = MagicMock()
        client._client.pages.retrieve.return_value = {
            "id": "page_id_123",
            "url": "https://notion.so/page_id_123",
            "properties": {
                "title": {
                    "title": [{"text": {"content": "Test Script Title"}}]
                }
            },
        }
        client._client.blocks.children.list.return_value = {
            "results": [
                {
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "Intro"}}]
                    },
                },
                {
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"text": {"content": "Welcome to the video"}}]
                    },
                },
                {
                    "type": "callout",
                    "callout": {
                        "rich_text": [{"text": {"content": "Talking head shot"}}],
                        "icon": {"type": "emoji", "emoji": "🔴"},
                        "color": "red",
                    },
                },
            ]
        }

        result = client.get_script("page_id_123")

        assert result["title"] == "Test Script Title"
        assert result["page_id"] == "page_id_123"
        assert len(result["sections"]) == 1
        assert result["sections"][0]["section_type"] == "Intro"
        assert result["sections"][0]["narration"] == "Welcome to the video"
        assert result["sections"][0]["visual_cue"] == "Talking head shot"
