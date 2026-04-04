"""
Phase 13 — Notion Integration Tests.

Comprehensive integration tests for the NotionScriptClient and color module
using REAL API credentials loaded from .env files.

Tests are designed to:
  - Pass when credentials are present AND the API call succeeds
  - Pass when credentials are missing (graceful degradation verified)
  - Fail when credentials are present but the API call fails unexpectedly

Run:
    pytest tests/integration/test_notion_integration.py -v
    pytest tests/integration/test_notion_integration.py -v -k "color"
    pytest tests/integration/test_notion_integration.py -v -k "not has_notion_credentials"  # unit-only
"""

from __future__ import annotations

import os
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
from packages.integrations.notion.client import NotionScriptClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_credentials() -> bool:
    """Check if real Notion credentials are available in the environment."""
    api_key = os.getenv("NOTION_API_KEY", "").strip()
    database_id = os.getenv("NOTION_DATABASE_ID", "").strip()
    return bool(api_key and database_id)


def _build_test_script_data(
    section_count: int = 1,
    visual_type: str = "talking_head",
) -> dict:
    """Build a minimal script_data dict matching the expected schema."""
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
    """Return a unique title to avoid collisions in Notion."""
    return f"Integration Test {int(time.time())}"


def _assert_success_result(
    result: OperationResult,
    msg: str = "OperationResult should be successful",
) -> None:
    """Assert an OperationResult represents success."""
    assert isinstance(result, OperationResult), f"{msg}: not an OperationResult instance"
    assert result.success is True, f"{msg}: success=False, error={result.error_message}"
    assert result.error_code is None, f"{msg}: unexpected error_code={result.error_code}"


def _assert_fail_result(
    result: OperationResult,
    expected_code: str | None = None,
    msg: str = "OperationResult should represent failure",
) -> None:
    """Assert an OperationResult represents failure."""
    assert isinstance(result, OperationResult), f"{msg}: not an OperationResult instance"
    assert result.success is False, f"{msg}: success=True but expected failure"
    assert result.error_message is not None and len(result.error_message) > 0, (
        f"{msg}: error_message should not be empty"
    )
    if expected_code is not None:
        assert result.error_code == expected_code, (
            f"{msg}: error_code={result.error_code!r}, expected={expected_code!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# A. Color Module Tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestColorModule:
    """Tests for packages.integrations.notion.colors."""

    def test_get_color_all_known_types(self):
        """Verify all 6 visual types return the correct Notion color strings."""
        expected = {
            "talking_head": "red",
            "animation": "blue",
            "broll": "green",
            "screen_recording": "yellow",
            "data_viz": "purple",
            "shader_bg": "gray",
        }
        for visual_type, expected_color in expected.items():
            assert visual_type in VISUAL_TYPE_COLORS, (
                f"Visual type '{visual_type}' missing from VISUAL_TYPE_COLORS"
            )
            result = get_color(visual_type)
            assert result == expected_color, (
                f"get_color({visual_type!r}) = {result!r}, expected {expected_color!r}"
            )

    def test_get_emoji_all_known_types(self):
        """Verify all 6 visual types return the correct emoji strings."""
        expected = {
            "talking_head": "\U0001f534",  # red circle
            "animation": "\U0001f535",    # blue circle
            "broll": "\U0001f7e2",        # green circle
            "screen_recording": "\U0001f7e1",  # yellow circle
            "data_viz": "\U0001f7e3",     # purple circle
            "shader_bg": "\u26ab",        # black circle
        }
        for visual_type, expected_emoji in expected.items():
            assert visual_type in EMOJI_MAP, (
                f"Visual type '{visual_type}' missing from EMOJI_MAP"
            )
            result = get_emoji(visual_type)
            assert result == expected_emoji, (
                f"get_emoji({visual_type!r}) = {result!r}, expected {expected_emoji!r}"
            )

    def test_color_unknown_type_returns_default(self):
        """Unknown visual types should return 'default' for color and a fallback emoji."""
        unknown = "nonexistent_visual_type"
        assert get_color(unknown) == "default", (
            f"get_color({unknown!r}) should return 'default'"
        )
        assert get_emoji(unknown) == "\u2b1c", (
            f"get_emoji({unknown!r}) should return white square fallback"
        )
        # Also test empty string
        assert get_color("") == "default"
        assert get_emoji("") == "\u2b1c"


# ═══════════════════════════════════════════════════════════════════════════
# B. Client Initialization Tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestClientInitialization:
    """Tests for NotionScriptClient.__init__."""

    def test_client_init_with_credentials(self, notion_config):
        """When credentials exist, the internal client should be initialized."""
        api_key = notion_config["api_key"]
        database_id = notion_config["database_id"]

        if not _has_credentials():
            # No credentials — verify degradation mode works
            client = NotionScriptClient(api_key="", database_id="")
            assert client._client is None, "Client should be None without API key"
            return

        client = NotionScriptClient(api_key=api_key, database_id=database_id)
        assert client._client is not None, (
            "Client should be initialized when valid API key is provided"
        )
        assert client.api_key == api_key
        assert client.database_id == database_id

    def test_client_init_without_credentials(self):
        """When no API key is provided, the client should remain None (degraded mode)."""
        client = NotionScriptClient(api_key="", database_id="")
        assert client._client is None, (
            "Client should be None when no API key is provided"
        )
        assert client.api_key == ""
        assert client.database_id == ""

    def test_client_init_uses_env_when_no_args(self):
        """When no arguments are passed, client reads from settings (env vars)."""
        client = NotionScriptClient()
        env_key = os.getenv("NOTION_API_KEY", "").strip()
        env_db = os.getenv("NOTION_DATABASE_ID", "").strip()

        if env_key:
            assert client._client is not None, (
                "Client should initialize from env NOTION_API_KEY"
            )
            assert client.api_key == env_key
        else:
            assert client._client is None, (
                "Client should be None when env NOTION_API_KEY is not set"
            )

        assert client.database_id == env_db


# ═══════════════════════════════════════════════════════════════════════════
# C. _check_client Tests (2 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestCheckClient:
    """Tests for NotionScriptClient._check_client."""

    def test_check_client_available(self, notion_config):
        """With a valid client, _check_client should return OperationResult.ok(None)."""
        api_key = notion_config["api_key"]

        if not api_key:
            # Cannot test availability without credentials — verify degradation path
            client = NotionScriptClient(api_key="", database_id="")
            result = client._check_client()
            _assert_fail_result(result, expected_code="NOTION_NOT_CONFIGURED",
                                msg="Missing credentials should return NOTION_NOT_CONFIGURED")
            return

        client = NotionScriptClient(api_key=api_key, database_id=notion_config["database_id"])
        result = client._check_client()
        _assert_success_result(result, msg="_check_client with valid credentials should succeed")
        assert result.data is None, "ok(None) should have data=None"

    def test_check_client_unavailable(self):
        """Without a client (no API key), _check_client should return NOTION_NOT_CONFIGURED."""
        client = NotionScriptClient(api_key="", database_id="")
        result = client._check_client()

        _assert_fail_result(result, expected_code="NOTION_NOT_CONFIGURED",
                            msg="No client should fail with NOTION_NOT_CONFIGURED")
        assert result.severity == ErrorSeverity.CRITICAL
        assert "Notion client is not initialized" in (result.error_message or "")


# ═══════════════════════════════════════════════════════════════════════════
# D. create_script_page Tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateScriptPage:
    """Tests for NotionScriptClient.create_script_page."""

    @pytest.mark.asyncio
    async def test_create_script_page_success(self, notion_config):
        """Create a real Notion page and verify the response contains a URL."""
        if not _has_credentials():
            client = NotionScriptClient(api_key="", database_id="")
            result = await client.create_script_page(
                title="Skipped — no credentials",
                script_data=_build_test_script_data(),
            )
            _assert_fail_result(result, expected_code="NOTION_NOT_CONFIGURED",
                                msg="Missing credentials should produce NOTION_NOT_CONFIGURED")
            return

        client = NotionScriptClient(
            api_key=notion_config["api_key"],
            database_id=notion_config["database_id"],
        )
        title = _unique_title()
        script_data = _build_test_script_data(section_count=1, visual_type="talking_head")

        result = await client.create_script_page(
            title=title,
            script_data=script_data,
            run_id="phase13-test-create",
        )

        _assert_success_result(result, msg="create_script_page should succeed with real credentials")
        assert result.data is not None and len(result.data) > 0, (
            "Success data should contain the page URL"
        )
        assert "notion.so" in result.data or "notion.site" in result.data, (
            f"Page URL should contain 'notion.so', got: {result.data}"
        )

    @pytest.mark.asyncio
    async def test_create_script_page_no_database_id(self, notion_config):
        """When database_id is empty, should fail with NOTION_NOT_CONFIGURED."""
        if not notion_config["api_key"]:
            # Can't test with no api key — but can test with api key and no db
            # We test the no-client path instead
            client = NotionScriptClient(api_key="", database_id="")
            result = await client.create_script_page(
                title="No DB test",
                script_data=_build_test_script_data(),
            )
            _assert_fail_result(result, expected_code="NOTION_NOT_CONFIGURED",
                                msg="No client should fail with NOTION_NOT_CONFIGURED")
            return

        # Initialize client with an API key but empty database_id
        client = NotionScriptClient(api_key=notion_config["api_key"], database_id="")
        result = await client.create_script_page(
            title="No DB test",
            script_data=_build_test_script_data(),
        )

        _assert_fail_result(result, expected_code="NOTION_NOT_CONFIGURED",
                            msg="Empty database_id should fail with NOTION_NOT_CONFIGURED")

    @pytest.mark.asyncio
    async def test_create_script_page_content_structure(self, notion_config):
        """Create a page then retrieve it to verify the block structure."""
        if not _has_credentials():
            # Verify that without credentials we get the expected degradation
            client = NotionScriptClient(api_key="", database_id="")
            result = await client.create_script_page(
                title="Structure test (no creds)",
                script_data=_build_test_script_data(),
            )
            _assert_fail_result(result, expected_code="NOTION_NOT_CONFIGURED")
            # Also verify get_script degradation
            get_result = await client.get_script("fake-page-id")
            _assert_fail_result(get_result, expected_code="NOTION_NOT_CONFIGURED")
            return

        client = NotionScriptClient(
            api_key=notion_config["api_key"],
            database_id=notion_config["database_id"],
        )
        title = _unique_title()
        section_type = "Hook"
        narration = "Welcome to this integration test video."
        visual_cue = "Close-up shot of the presenter."
        visual_type = "talking_head"

        script_data = {
            "entries": [{
                "section_type": section_type,
                "narration": narration,
                "visual_cue": visual_cue,
                "visual_type": visual_type,
            }],
        }

        create_result = await client.create_script_page(
            title=title,
            script_data=script_data,
            run_id="phase13-test-structure",
        )
        _assert_success_result(create_result, msg="Page creation should succeed")

        # Extract page_id from URL (URL format: https://notion.so/Title-<32-char-id>)
        page_url = create_result.data
        page_id = page_url.rstrip("/").split("-")[-1]
        # Notion IDs are 32 hex chars, but URL may add dashes
        if len(page_id) != 32:
            # Try extracting differently — the ID is the part after the last hyphen
            # and may be 32 chars without dashes (URL format removes dashes)
            pass

        # Retrieve the page and verify content
        get_result = await client.get_script(page_id)
        _assert_success_result(get_result, msg="get_script should retrieve the created page")

        retrieved = get_result.data
        assert isinstance(retrieved, dict), "Retrieved data should be a dict"

        # Verify sections were parsed correctly
        sections = retrieved.get("sections", [])
        assert len(sections) >= 1, (
            f"Expected at least 1 section, got {len(sections)}"
        )

        first_section = sections[0]
        assert first_section.get("section_type") == section_type, (
            f"Section type mismatch: {first_section.get('section_type')!r} != {section_type!r}"
        )
        assert narration in first_section.get("narration", ""), (
            f"Narration not found in section: {first_section.get('narration')!r}"
        )
        assert visual_cue in first_section.get("visual_cue", ""), (
            f"Visual cue not found in section: {first_section.get('visual_cue')!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# E. update_script_page Tests (2 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestUpdateScriptPage:
    """Tests for NotionScriptClient.update_script_page."""

    @pytest.mark.asyncio
    async def test_update_script_page_success(self, notion_config):
        """Create a page, then update it with new sections and verify success."""
        if not _has_credentials():
            client = NotionScriptClient(api_key="", database_id="")
            result = await client.update_script_page(
                page_id="fake-id",
                sections=_build_test_script_data()["entries"],
            )
            _assert_fail_result(result, expected_code="NOTION_NOT_CONFIGURED",
                                msg="Missing credentials should fail with NOTION_NOT_CONFIGURED")
            return

        client = NotionScriptClient(
            api_key=notion_config["api_key"],
            database_id=notion_config["database_id"],
        )

        # Step 1: Create a page first
        create_result = await client.create_script_page(
            title=_unique_title(),
            script_data=_build_test_script_data(section_count=1, visual_type="broll"),
            run_id="phase13-test-update",
        )
        _assert_success_result(create_result, msg="Page creation should succeed")

        page_url = create_result.data
        page_id = page_url.rstrip("/").split("-")[-1]

        # Step 2: Update the page with a new section
        new_sections = [{
            "section_type": "Updated Section",
            "narration": "This is the appended content from update_script_page.",
            "visual_cue": "New visual cue added via update.",
            "visual_type": "animation",
        }]

        update_result = await client.update_script_page(
            page_id=page_id,
            sections=new_sections,
            run_id="phase13-test-update",
        )
        _assert_success_result(update_result, msg="update_script_page should succeed")

    @pytest.mark.asyncio
    async def test_update_script_page_no_client(self):
        """Without a client, update_script_page should fail with NOTION_NOT_CONFIGURED."""
        client = NotionScriptClient(api_key="", database_id="")
        result = await client.update_script_page(
            page_id="some-fake-page-id",
            sections=[{"section_type": "Test", "narration": "Test", "visual_cue": "Test", "visual_type": "talking_head"}],
        )

        _assert_fail_result(result, expected_code="NOTION_NOT_CONFIGURED",
                            msg="No client should fail with NOTION_NOT_CONFIGURED")


# ═══════════════════════════════════════════════════════════════════════════
# F. get_script Tests (2 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestGetScript:
    """Tests for NotionScriptClient.get_script."""

    @pytest.mark.asyncio
    async def test_get_script_success(self, notion_config):
        """Create a page, then retrieve it and verify the parsed structure."""
        if not _has_credentials():
            client = NotionScriptClient(api_key="", database_id="")
            result = await client.get_script("fake-page-id")
            _assert_fail_result(result, expected_code="NOTION_NOT_CONFIGURED",
                                msg="Missing credentials should fail with NOTION_NOT_CONFIGURED")
            return

        client = NotionScriptClient(
            api_key=notion_config["api_key"],
            database_id=notion_config["database_id"],
        )

        # Create a page with known content
        title = _unique_title()
        script_data = _build_test_script_data(section_count=2, visual_type="data_viz")
        create_result = await client.create_script_page(
            title=title,
            script_data=script_data,
            run_id="phase13-test-get",
        )
        _assert_success_result(create_result, msg="Page creation should succeed")

        page_url = create_result.data
        page_id = page_url.rstrip("/").split("-")[-1]

        # Retrieve the page
        get_result = await client.get_script(page_id)
        _assert_success_result(get_result, msg="get_script should succeed")

        retrieved = get_result.data
        assert isinstance(retrieved, dict)
        assert retrieved.get("page_id") == page_id
        assert len(retrieved.get("sections", [])) == 2, (
            f"Expected 2 sections, got {len(retrieved.get('sections', []))}"
        )

        # Verify first section has correct narration
        first_section = retrieved["sections"][0]
        assert "narration text for section 1" in first_section.get("narration", ""), (
            f"First section narration mismatch: {first_section.get('narration')!r}"
        )

    @pytest.mark.asyncio
    async def test_get_script_no_client(self):
        """Without a client, get_script should fail with NOTION_NOT_CONFIGURED."""
        client = NotionScriptClient(api_key="", database_id="")
        result = await client.get_script("nonexistent-page-id")

        _assert_fail_result(result, expected_code="NOTION_NOT_CONFIGURED",
                            msg="No client should fail with NOTION_NOT_CONFIGURED")
        assert result.user_message is not None and len(result.user_message) > 0


# ═══════════════════════════════════════════════════════════════════════════
# G. Error Handling Tests (2 tests)
# ═══════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Tests for error handling paths and OperationResult structure."""

    @pytest.mark.asyncio
    async def test_create_page_with_bad_api_key(self):
        """Invalid API key should produce OperationResult.fail with an appropriate error code.

        When notion_client is NOT installed, the client can't be created at all,
        so we get NOTION_NOT_CONFIGURED. When it IS installed but the key is bad,
        we get NOTION_AUTH_FAILED or NOTION_PUBLISH_FAILED from the API.
        """
        client = NotionScriptClient(api_key="ntn_invalid_key_12345", database_id="fake-db-id")

        # If notion_client is not installed, _client will be None
        # and the method returns NOTION_NOT_CONFIGURED before hitting the API.
        if client._client is None:
            # notion_client package not installed — verify graceful degradation
            result = await client.create_script_page(
                title="Bad Key Test",
                script_data=_build_test_script_data(),
                run_id="phase13-test-bad-key",
            )
            _assert_fail_result(
                result,
                expected_code="NOTION_NOT_CONFIGURED",
                msg="Without notion_client installed, should degrade gracefully",
            )
            assert result.severity == ErrorSeverity.CRITICAL
            return

        # notion_client IS installed — bad key should cause an API-level failure
        result = await client.create_script_page(
            title="Bad Key Test",
            script_data=_build_test_script_data(),
            run_id="phase13-test-bad-key",
        )

        _assert_fail_result(result, msg="Bad API key should produce a failure result")

        assert result.error_code in (
            "NOTION_AUTH_FAILED",
            "NOTION_PUBLISH_FAILED",
            "NOTION_NOT_CONFIGURED",
        ), f"Unexpected error_code for bad key: {result.error_code!r}"

        assert result.severity is not None, "Severity should be set on failure"
        assert result.user_message is not None and len(result.user_message) > 0, (
            "user_message should be populated"
        )

    @pytest.mark.asyncio
    async def test_operation_result_structure(self, notion_config):
        """Verify all OperationResult attributes exist on both ok and fail responses."""
        # Test success result structure
        ok_result = OperationResult.ok(
            data="https://notion.so/test-page",
            message="Test success message",
        )
        assert ok_result.success is True
        assert ok_result.data == "https://notion.so/test-page"
        assert ok_result.user_message == "Test success message"
        assert ok_result.error_code is None
        assert ok_result.error_message is None
        assert ok_result.retryable is False
        assert ok_result.retry_after_seconds is None
        assert isinstance(ok_result.error_details, dict)

        # Test failure result structure
        fail_result = OperationResult.fail(
            message="Internal error occurred",
            code="NOTION_PUBLISH_FAILED",
            severity=ErrorSeverity.CRITICAL,
            user_message="Could not publish to Notion.",
            retryable=True,
            retry_after=60,
            details={"attempt": 3, "last_error": "timeout"},
        )
        assert fail_result.success is False
        assert fail_result.error_message == "Internal error occurred"
        assert fail_result.error_code == "NOTION_PUBLISH_FAILED"
        assert fail_result.severity == ErrorSeverity.CRITICAL
        assert fail_result.user_message == "Could not publish to Notion."
        assert fail_result.retryable is True
        assert fail_result.retry_after_seconds == 60
        assert fail_result.error_details == {"attempt": 3, "last_error": "timeout"}

        # Test to_api_response on success
        api_ok = ok_result.to_api_response()
        assert api_ok["success"] is True
        assert api_ok["data"] == "https://notion.so/test-page"
        assert api_ok["message"] == "Test success message"

        # Test to_api_response on failure
        api_fail = fail_result.to_api_response()
        assert api_fail["success"] is False
        assert api_fail["error_code"] == "NOTION_PUBLISH_FAILED"
        assert api_fail["severity"] == "critical"
        assert api_fail["retryable"] is True
        assert api_fail["retry_after_seconds"] == 60

        # Verify real Notion client produces OperationResult with correct structure
        if _has_credentials():
            client = NotionScriptClient(
                api_key=notion_config["api_key"],
                database_id=notion_config["database_id"],
            )
            result = await client.create_script_page(
                title=_unique_title(),
                script_data=_build_test_script_data(),
                run_id="phase13-test-structure",
            )
            assert hasattr(result, "success"), "Result should have 'success' attribute"
            assert hasattr(result, "data"), "Result should have 'data' attribute"
            assert hasattr(result, "error_code"), "Result should have 'error_code' attribute"
            assert hasattr(result, "error_message"), "Result should have 'error_message' attribute"
            assert hasattr(result, "severity"), "Result should have 'severity' attribute"
            assert hasattr(result, "user_message"), "Result should have 'user_message' attribute"
            assert hasattr(result, "retryable"), "Result should have 'retryable' attribute"
        else:
            # Even with degraded client, result should have all attributes
            client = NotionScriptClient(api_key="", database_id="")
            result = await client.create_script_page(
                title="structure test",
                script_data=_build_test_script_data(),
            )
            assert hasattr(result, "success")
            assert hasattr(result, "data")
            assert hasattr(result, "error_code")
            assert hasattr(result, "error_message")
            assert hasattr(result, "severity")
            assert hasattr(result, "user_message")
            assert hasattr(result, "retryable")
