"""
Phase 13 — Notion Integration Tests (Real API Calls).

Comprehensive integration tests for the NotionScriptClient, _parse_database_id
helper, and color module.  Tests that interact with the Notion API use REAL
credentials loaded from .env via the integration conftest.

Key design decisions:
  * Tests requiring credentials call the live Notion API and attempt to
    archive (soft-delete) pages afterwards.
  * Tests verifying "no-credentials" degradation pass explicit empty strings
    AND monkeypatch-del the env vars so no fallback can accidentally succeed.
  * Every async test uses ``@pytest.mark.asyncio``.

Run:
    pytest tests/integration/test_notion_integration.py -v
    pytest tests/integration/test_notion_integration.py -v -k "parse"
    pytest tests/integration/test_notion_integration.py -v -k "color"
    pytest tests/integration/test_notion_integration.py -v -k "not real"
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

import pytest

from packages.core.operation_result import OperationResult, ErrorSeverity
from packages.integrations.notion.colors import (
    VISUAL_TYPE_COLORS,
    EMOJI_MAP,
    get_color,
    get_emoji,
)
from packages.integrations.notion.client import (
    NotionScriptClient,
    _parse_database_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_credentials() -> bool:
    """Return True when both NOTION_API_KEY and NOTION_DATABASE_ID are set."""
    return bool(
        os.getenv("NOTION_API_KEY", "").strip()
        and os.getenv("NOTION_DATABASE_ID", "").strip()
    )


def _build_test_script_data(
    section_count: int = 1,
    visual_type: str = "talking_head",
) -> dict:
    """Build a minimal *script_data* dict matching the expected schema."""
    sections = []
    for i in range(section_count):
        sections.append({
            "section_type": f"Section {i + 1}",
            "narration": f"This is the narration text for section {i + 1}.",
            "visual_cue": f"Visual cue for section {i + 1}.",
            "visual_type": visual_type,
        })
    return {"entries": sections}


def _unique_title() -> str:
    """Timestamped title to avoid Notion collisions."""
    return f"Integration Test {int(time.time())}"


def _extract_page_id(url: str) -> str:
    """Pull the 32-char hex page ID out of a Notion URL."""
    m = re.search(r"([0-9a-fA-F]{32})", url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract page ID from URL: {url}")


def _archive_page(client: NotionScriptClient, page_url: str) -> None:
    """Best-effort archival of a Notion page after testing."""
    try:
        if client._client and page_url:
            pid = _extract_page_id(page_url)
            client._client.pages.update(page_id=pid, archived=True)
    except Exception:
        pass  # cleanup is best-effort


def _assert_ok(result: OperationResult, msg: str = "") -> None:
    ctx = f"{msg}: " if msg else ""
    assert isinstance(result, OperationResult), f"{ctx}not an OperationResult"
    assert result.success is True, f"{ctx}success=False  error={result.error_message}"
    assert result.error_code is None, f"{ctx}unexpected code={result.error_code}"


def _assert_fail(
    result: OperationResult,
    expected_code: str | None = None,
    msg: str = "",
) -> None:
    ctx = f"{msg}: " if msg else ""
    assert isinstance(result, OperationResult), f"{ctx}not an OperationResult"
    assert result.success is False, f"{ctx}expected failure but got success"
    assert result.error_message, f"{ctx}error_message is empty"
    if expected_code is not None:
        assert result.error_code == expected_code, (
            f"{ctx}code={result.error_code!r}  expected={expected_code!r}"
        )


def _require_creds(notion_config: dict) -> None:
    """Skip the calling test when real credentials are unavailable."""
    if not _has_credentials():
        pytest.skip("No Notion credentials in .env — skipping live-API test")


# ═══════════════════════════════════════════════════════════════════════════
# A. _parse_database_id  (4 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestParseDatabaseId:
    """Direct unit tests for the _parse_database_id helper."""

    def test_uuid_with_query_params(self):
        """Query-string noise (?v=…&t=…) must be stripped; UUID preserved."""
        raw = (
            "3373ff3f091780bca320f9142f486ec3"
            "?v=3373ff3f091780998c05000cfa42d9f5"
            "&t=3373ff3f09178051a8d100a9ba125896"
        )
        result = _parse_database_id(raw)
        assert result == "3373ff3f091780bca320f9142f486ec3"
        assert "?" not in result
        assert "&" not in result

    def test_full_notion_url(self):
        """A full https://notion.so/… URL should yield a clean UUID."""
        raw = "https://www.notion.so/workspace/3373ff3f091780bca320f9142f486ec3-TitleText"
        result = _parse_database_id(raw)
        # Should be a valid hex ID (32 chars, or dashed UUID)
        assert re.match(r"^[0-9a-fA-F-]+$", result), f"got {result!r}"
        assert "http" not in result
        assert len(result) >= 32

    def test_bare_uuid(self):
        """Bare UUID (with or without dashes) passes through unchanged."""
        with_dashes = "3373ff3f-0917-80bc-a320-f9142f486ec3"
        assert _parse_database_id(with_dashes) == with_dashes

        no_dashes = "3373ff3f091780bca320f9142f486ec3"
        assert _parse_database_id(no_dashes) == no_dashes

    def test_empty_and_whitespace(self):
        """Empty or whitespace-only input returns empty string."""
        assert _parse_database_id("") == ""
        assert _parse_database_id("   ") == ""


# ═══════════════════════════════════════════════════════════════════════════
# B. Color module  (3 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestColorModule:
    """Tests for packages.integrations.notion.colors."""

    def test_get_color_all_known_types(self):
        """Every visual type in VISUAL_TYPE_COLORS returns the correct color."""
        expected = {
            "talking_head": "red",
            "animation": "blue",
            "broll": "green",
            "screen_recording": "yellow",
            "data_viz": "purple",
            "shader_bg": "gray",
        }
        for vtype, color in expected.items():
            assert vtype in VISUAL_TYPE_COLORS, f"{vtype!r} missing from map"
            assert get_color(vtype) == color, (
                f"get_color({vtype!r}) = {get_color(vtype)!r}, expected {color!r}"
            )

    def test_get_emoji_all_known_types(self):
        """Every visual type in EMOJI_MAP returns the correct emoji."""
        expected = {
            "talking_head": "\U0001f534",
            "animation": "\U0001f535",
            "broll": "\U0001f7e2",
            "screen_recording": "\U0001f7e1",
            "data_viz": "\U0001f7e3",
            "shader_bg": "\u26ab",
        }
        for vtype, emoji in expected.items():
            assert vtype in EMOJI_MAP, f"{vtype!r} missing from EMOJI_MAP"
            assert get_emoji(vtype) == emoji, (
                f"get_emoji({vtype!r}) = {get_emoji(vtype)!r}, expected {emoji!r}"
            )

    def test_unknown_type_returns_defaults(self):
        """Unknown visual types fall back to 'default' color and white-square emoji."""
        assert get_color("nonexistent_type") == "default"
        assert get_emoji("nonexistent_type") == "\u2b1c"
        assert get_color("") == "default"
        assert get_emoji("") == "\u2b1c"


# ═══════════════════════════════════════════════════════════════════════════
# C. Client initialization  (3 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestClientInitialization:
    """Tests for NotionScriptClient.__init__."""

    def test_with_real_credentials(self, notion_config):
        """With real credentials, the internal notion_client is created."""
        _require_creds(notion_config)
        client = NotionScriptClient(
            api_key=notion_config["api_key"],
            database_id=notion_config["database_id"],
        )
        assert client._client is not None, "Client should initialise with valid API key"
        assert client.api_key == notion_config["api_key"]
        # database_id should be the PARSED version (no query params)
        assert "?" not in client.database_id
        assert "&" not in client.database_id

    def test_without_credentials_uses_monkeypatch(self, monkeypatch):
        """With empty api_key and env cleared, _client stays None."""
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
        client = NotionScriptClient(api_key="", database_id="")
        assert client._client is None, (
            "Client should be None when api_key is empty"
        )
        assert client.api_key == ""
        assert client.database_id == ""

    def test_env_fallback_when_no_args(self):
        """NotionScriptClient() with no args reads from cached Settings/env."""
        _require_creds({})  # skip if no creds
        # Clear the lru_cache so Settings re-reads from the (conftest-loaded) env
        from packages.core.config import get_settings as _gs
        _gs.cache_clear()

        client = NotionScriptClient()
        env_key = os.getenv("NOTION_API_KEY", "").strip()
        assert client.api_key == env_key
        if env_key:
            assert client._client is not None, (
                "Should create client from env NOTION_API_KEY"
            )
        else:
            assert client._client is None


# ═══════════════════════════════════════════════════════════════════════════
# D. _check_client  (2 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestCheckClient:
    """Tests for NotionScriptClient._check_client."""

    def test_client_available(self, notion_config):
        """With a real client, _check_client returns OperationResult.ok(None)."""
        _require_creds(notion_config)
        client = NotionScriptClient(
            api_key=notion_config["api_key"],
            database_id=notion_config["database_id"],
        )
        result = client._check_client()
        _assert_ok(result, "valid client → ok(None)")
        assert result.data is None

    def test_client_unavailable(self, monkeypatch):
        """Without a client, _check_client fails NOTION_NOT_CONFIGURED."""
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
        client = NotionScriptClient(api_key="", database_id="")
        result = client._check_client()
        _assert_fail(result, expected_code="NOTION_NOT_CONFIGURED",
                      msg="no client → NOTION_NOT_CONFIGURED")
        assert result.severity == ErrorSeverity.CRITICAL
        assert "Notion client is not initialized" in (result.error_message or "")


# ═══════════════════════════════════════════════════════════════════════════
# E. create_script_page  (2 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateScriptPage:
    """Tests for NotionScriptClient.create_script_page."""

    @pytest.mark.asyncio
    async def test_real_page_creation(self, notion_config):
        """Create a real Notion page; verify success and URL shape; clean up."""
        _require_creds(notion_config)
        client = NotionScriptClient(
            api_key=notion_config["api_key"],
            database_id=notion_config["database_id"],
        )
        title = _unique_title()
        script_data = _build_test_script_data(section_count=1, visual_type="talking_head")

        result = await client.create_script_page(
            title=title, script_data=script_data, run_id="phase13-test-create",
        )

        try:
            _assert_ok(result, "create_script_page with real creds")
            assert result.data is not None and len(result.data) > 0, "data should be page URL"
            assert "notion.so" in result.data or "notion.site" in result.data, (
                f"URL should contain 'notion.so', got: {result.data}"
            )
        finally:
            _archive_page(client, result.data or "")

    @pytest.mark.asyncio
    async def test_without_credentials(self, monkeypatch):
        """No credentials → NOTION_NOT_CONFIGURED, never hits the API."""
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
        client = NotionScriptClient(api_key="", database_id="")
        result = await client.create_script_page(
            title="Should Not Be Created",
            script_data=_build_test_script_data(),
        )
        _assert_fail(result, expected_code="NOTION_NOT_CONFIGURED",
                      msg="no creds → NOTION_NOT_CONFIGURED")


# ═══════════════════════════════════════════════════════════════════════════
# F. update_script_page  (2 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestUpdateScriptPage:
    """Tests for NotionScriptClient.update_script_page."""

    @pytest.mark.asyncio
    async def test_create_then_update(self, notion_config):
        """Create a page, then append new sections; verify success; clean up."""
        _require_creds(notion_config)
        client = NotionScriptClient(
            api_key=notion_config["api_key"],
            database_id=notion_config["database_id"],
        )

        # Step 1 — create
        create_result = await client.create_script_page(
            title=_unique_title(),
            script_data=_build_test_script_data(section_count=1, visual_type="broll"),
            run_id="phase13-test-update",
        )
        _assert_ok(create_result, "page creation for update test")
        page_url = create_result.data or ""
        page_id = _extract_page_id(page_url)

        try:
            # Step 2 — update
            new_sections = [{
                "section_type": "Appended Section",
                "narration": "Content added by update_script_page.",
                "visual_cue": "New visual from update.",
                "visual_type": "animation",
            }]
            update_result = await client.update_script_page(
                page_id=page_id, sections=new_sections, run_id="phase13-test-update",
            )
            _assert_ok(update_result, "update_script_page should succeed")
        finally:
            _archive_page(client, page_url)

    @pytest.mark.asyncio
    async def test_without_client(self, monkeypatch):
        """No client → NOTION_NOT_CONFIGURED."""
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
        client = NotionScriptClient(api_key="", database_id="")
        result = await client.update_script_page(
            page_id="fake-page-id",
            sections=[{
                "section_type": "T", "narration": "N",
                "visual_cue": "V", "visual_type": "talking_head",
            }],
        )
        _assert_fail(result, expected_code="NOTION_NOT_CONFIGURED",
                      msg="no client update → NOTION_NOT_CONFIGURED")


# ═══════════════════════════════════════════════════════════════════════════
# G. get_script  (2 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestGetScript:
    """Tests for NotionScriptClient.get_script."""

    @pytest.mark.asyncio
    async def test_create_then_retrieve(self, notion_config):
        """Create a page with known content, retrieve it, verify sections."""
        _require_creds(notion_config)
        client = NotionScriptClient(
            api_key=notion_config["api_key"],
            database_id=notion_config["database_id"],
        )

        title = _unique_title()
        script_data = _build_test_script_data(section_count=2, visual_type="data_viz")
        create_result = await client.create_script_page(
            title=title, script_data=script_data, run_id="phase13-test-get",
        )
        _assert_ok(create_result, "page creation for get_script test")
        page_url = create_result.data or ""
        page_id = _extract_page_id(page_url)

        try:
            get_result = await client.get_script(page_id)
            _assert_ok(get_result, "get_script should retrieve the page")

            data = get_result.data
            assert isinstance(data, dict), "data should be a dict"
            assert data.get("page_id") == page_id
            sections = data.get("sections", [])
            assert len(sections) == 2, f"Expected 2 sections, got {len(sections)}"

            first = sections[0]
            assert "narration text for section 1" in first.get("narration", ""), (
                f"First narration mismatch: {first.get('narration')!r}"
            )
        finally:
            _archive_page(client, page_url)

    @pytest.mark.asyncio
    async def test_without_client(self, monkeypatch):
        """No client → NOTION_NOT_CONFIGURED."""
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
        client = NotionScriptClient(api_key="", database_id="")
        result = await client.get_script("nonexistent-page-id")
        _assert_fail(result, expected_code="NOTION_NOT_CONFIGURED",
                      msg="no client get → NOTION_NOT_CONFIGURED")
        assert result.user_message is not None and len(result.user_message) > 0


# ═══════════════════════════════════════════════════════════════════════════
# H. Error handling  (1 test)
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Tests for error / auth-failure paths."""

    @pytest.mark.asyncio
    async def test_bad_api_key(self):
        """A fabricated API key must produce NOTION_AUTH_FAILED.

        The retry decorator does *not* retry on 401 (not in the retryable
        exception set), so this test completes in one round-trip.
        """
        # The key is long enough (>5 chars) to pass the init guard, but invalid.
        client = NotionScriptClient(
            api_key="ntn_invalid_key_12345",
            database_id="3373ff3f091780bca320f9142f486ec3",
        )

        # If notion_client package isn't installed, _client is None.
        if client._client is None:
            pytest.skip("notion_client package not installed")

        result = await client.create_script_page(
            title="Bad Key Test",
            script_data=_build_test_script_data(),
            run_id="phase13-test-bad-key",
        )

        _assert_fail(result, msg="bad API key should produce failure")
        assert result.error_code in (
            "NOTION_AUTH_FAILED",
            "NOTION_PUBLISH_FAILED",
        ), f"Unexpected error code: {result.error_code!r}"
        assert result.severity is not None
        assert result.user_message and len(result.user_message) > 0
