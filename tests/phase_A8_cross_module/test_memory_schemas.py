"""Tests for packages/memory/schemas.py — Memory metadata schemas."""

import pytest
from datetime import datetime, timezone


class TestVideoSessionMetadata:
    """Tests for VIDEO_SESSION_METADATA schema."""

    def test_exists(self):
        from packages.memory.schemas import VIDEO_SESSION_METADATA
        assert VIDEO_SESSION_METADATA is not None

    def test_is_dict(self):
        from packages.memory.schemas import VIDEO_SESSION_METADATA
        assert isinstance(VIDEO_SESSION_METADATA, dict)

    def test_has_session_type(self):
        from packages.memory.schemas import VIDEO_SESSION_METADATA
        assert VIDEO_SESSION_METADATA["session_type"] == "video_production"

    def test_extensible(self):
        from packages.memory.schemas import VIDEO_SESSION_METADATA
        extended = {**VIDEO_SESSION_METADATA, "video_topic": "Test Topic"}
        assert extended["session_type"] == "video_production"
        assert extended["video_topic"] == "Test Topic"

    def test_does_not_mutate_original(self):
        from packages.memory.schemas import VIDEO_SESSION_METADATA
        original_len = len(VIDEO_SESSION_METADATA)
        _ = {**VIDEO_SESSION_METADATA, "extra_field": "value"}
        assert len(VIDEO_SESSION_METADATA) == original_len


class TestChannelUserMetadata:
    """Tests for CHANNEL_USER_METADATA schema."""

    def test_exists(self):
        from packages.memory.schemas import CHANNEL_USER_METADATA
        assert CHANNEL_USER_METADATA is not None

    def test_is_dict(self):
        from packages.memory.schemas import CHANNEL_USER_METADATA
        assert isinstance(CHANNEL_USER_METADATA, dict)

    def test_has_user_type(self):
        from packages.memory.schemas import CHANNEL_USER_METADATA
        assert CHANNEL_USER_METADATA["user_type"] == "channel_owner"

    def test_extensible_with_channel_info(self):
        from packages.memory.schemas import CHANNEL_USER_METADATA
        extended = {
            **CHANNEL_USER_METADATA,
            "channel_name": "Pakistani Explainer",
            "audience_primary": "Pakistani youth",
        }
        assert extended["user_type"] == "channel_owner"
        assert extended["channel_name"] == "Pakistani Explainer"


class TestAnalyticsSessionMetadata:
    """Tests for ANALYTICS_SESSION_METADATA schema."""

    def test_exists(self):
        from packages.memory.schemas import ANALYTICS_SESSION_METADATA
        assert ANALYTICS_SESSION_METADATA is not None

    def test_is_dict(self):
        from packages.memory.schemas import ANALYTICS_SESSION_METADATA
        assert isinstance(ANALYTICS_SESSION_METADATA, dict)

    def test_has_session_type(self):
        from packages.memory.schemas import ANALYTICS_SESSION_METADATA
        assert ANALYTICS_SESSION_METADATA["session_type"] == "analytics_feedback"

    def test_extensible_with_analytics_data(self):
        from packages.memory.schemas import ANALYTICS_SESSION_METADATA
        extended = {
            **ANALYTICS_SESSION_METADATA,
            "video_id": "abc123",
            "views": 50000,
            "ctr": 4.5,
            "retention": 65.2,
        }
        assert extended["session_type"] == "analytics_feedback"
        assert extended["video_id"] == "abc123"
        assert extended["views"] == 50000


class TestSchemaRelationships:
    """Tests for relationships between schemas."""

    def test_all_schemas_are_dicts(self):
        from packages.memory.schemas import (
            VIDEO_SESSION_METADATA, CHANNEL_USER_METADATA, ANALYTICS_SESSION_METADATA
        )
        for schema in [VIDEO_SESSION_METADATA, CHANNEL_USER_METADATA, ANALYTICS_SESSION_METADATA]:
            assert isinstance(schema, dict)

    def test_session_types_are_different(self):
        from packages.memory.schemas import (
            VIDEO_SESSION_METADATA, ANALYTICS_SESSION_METADATA
        )
        assert VIDEO_SESSION_METADATA["session_type"] != ANALYTICS_SESSION_METADATA["session_type"]

    def test_schemas_are_independent_copies(self):
        from packages.memory.schemas import (
            VIDEO_SESSION_METADATA, CHANNEL_USER_METADATA
        )
        # Modifying one should not affect the other
        _ = {**VIDEO_SESSION_METADATA, "extra": "test"}
        assert "extra" not in VIDEO_SESSION_METADATA
        assert "extra" not in CHANNEL_USER_METADATA
