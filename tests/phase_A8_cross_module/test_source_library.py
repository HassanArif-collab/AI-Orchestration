"""Tests for packages/content_factory/source_library.py — Source video library."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch


class TestSourceVideoLibraryInit:
    """Tests for SourceVideoLibrary initialization."""

    def test_init_creates_directory(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary
        nested = tmp_path / "sub" / "dir" / "test.db"
        lib = SourceVideoLibrary(db_path=str(nested))
        assert nested.parent.exists()

    def test_init_creates_table(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary
        db_path = str(tmp_path / "test.db")
        lib = SourceVideoLibrary(db_path=db_path)
        # Should not raise
        assert lib.db_path == db_path


class TestSourceVideoLibraryCRUD:
    """Tests for SourceVideoLibrary CRUD operations."""

    @pytest.fixture()
    def library(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary
        db_path = str(tmp_path / "test.db")
        return SourceVideoLibrary(db_path=db_path)

    @pytest.fixture()
    def sample_record(self):
        from packages.content_factory.source_library import SourceVideoRecord
        return SourceVideoRecord(
            video_id="abc123",
            url="https://youtube.com/watch?v=abc123",
            title="Test Video",
            views=5000,
            genre="tech",
            processing_status="extracted_only",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def test_exists_false(self, library):
        assert library.exists("nonexistent") is False

    def test_save_and_exists(self, library, sample_record):
        library.save(sample_record)
        assert library.exists("abc123") is True

    def test_save_and_load(self, library, sample_record):
        library.save(sample_record)
        loaded = library.load("abc123")
        assert loaded is not None
        assert loaded.video_id == "abc123"
        assert loaded.title == "Test Video"
        assert loaded.views == 5000

    def test_load_nonexistent(self, library):
        assert library.load("nonexistent") is None

    def test_save_updates_existing(self, library, sample_record):
        library.save(sample_record)
        sample_record.title = "Updated Title"
        library.save(sample_record)
        loaded = library.load("abc123")
        assert loaded.title == "Updated Title"


class TestUpdateStatus:
    """Tests for update_status()."""

    def test_update_status_existing(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary, SourceVideoRecord
        from packages.content_factory.models import ProcessingStatus

        lib = SourceVideoLibrary(db_path=str(tmp_path / "test.db"))
        record = SourceVideoRecord(
            video_id="abc123",
            url="https://youtube.com",
            title="Test",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        lib.save(record)
        lib.update_status("abc123", ProcessingStatus.FULLY_ANALYZED)

        loaded = lib.load("abc123")
        assert loaded.processing_status == ProcessingStatus.FULLY_ANALYZED

    def test_update_status_nonexistent(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary
        from packages.content_factory.models import ProcessingStatus

        lib = SourceVideoLibrary(db_path=str(tmp_path / "test.db"))
        # Should not raise, just log warning
        lib.update_status("nonexistent", ProcessingStatus.ADAPTED)


class TestListVideos:
    """Tests for list_videos()."""

    def test_empty_library(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary
        lib = SourceVideoLibrary(db_path=str(tmp_path / "test.db"))
        result = lib.list_videos()
        assert result == []

    def test_returns_all_videos(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary, SourceVideoRecord
        from packages.content_factory.models import ProcessingStatus

        lib = SourceVideoLibrary(db_path=str(tmp_path / "test.db"))
        now = datetime.now(timezone.utc)
        for i in range(3):
            record = SourceVideoRecord(
                video_id=f"vid{i}",
                url=f"https://youtube.com/watch?v=vid{i}",
                title=f"Video {i}",
                created_at=now,
                updated_at=now,
            )
            lib.save(record)

        result = lib.list_videos()
        assert len(result) == 3

    def test_filter_by_status(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary, SourceVideoRecord
        from packages.content_factory.models import ProcessingStatus

        lib = SourceVideoLibrary(db_path=str(tmp_path / "test.db"))
        now = datetime.now(timezone.utc)

        r1 = SourceVideoRecord(
            video_id="v1", url="u1", title="T1",
            processing_status=ProcessingStatus.EXTRACTED_ONLY,
            created_at=now, updated_at=now,
        )
        r2 = SourceVideoRecord(
            video_id="v2", url="u2", title="T2",
            processing_status=ProcessingStatus.FULLY_ANALYZED,
            created_at=now, updated_at=now,
        )
        lib.save(r1)
        lib.save(r2)

        result = lib.list_videos(status=ProcessingStatus.FULLY_ANALYZED)
        assert len(result) == 1
        assert result[0]["video_id"] == "v2"

    def test_limit_param(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary, SourceVideoRecord

        lib = SourceVideoLibrary(db_path=str(tmp_path / "test.db"))
        now = datetime.now(timezone.utc)
        for i in range(5):
            lib.save(SourceVideoRecord(
                video_id=f"v{i}", url=f"u{i}", title=f"T{i}",
                created_at=now, updated_at=now,
            ))

        result = lib.list_videos(limit=2)
        assert len(result) == 2


class TestFindByGenre:
    """Tests for find_by_genre()."""

    def test_filters_by_genre(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary, SourceVideoRecord
        from packages.content_factory.models import ProcessingStatus

        lib = SourceVideoLibrary(db_path=str(tmp_path / "test.db"))
        now = datetime.now(timezone.utc)

        for i, (vid, genre, status) in enumerate([
            ("v1", "tech", ProcessingStatus.FULLY_ANALYZED),
            ("v2", "history", ProcessingStatus.FULLY_ANALYZED),
            ("v3", "tech", ProcessingStatus.ADAPTED),
        ]):
            lib.save(SourceVideoRecord(
                video_id=vid, url=f"u{vid}", title=f"T{vid}",
                genre=genre, processing_status=status,
                created_at=now, updated_at=now,
            ))

        results = lib.find_by_genre("tech")
        assert len(results) == 2
        assert all(r.genre == "tech" for r in results)

    def test_empty_genre(self, tmp_path):
        from packages.content_factory.source_library import SourceVideoLibrary
        lib = SourceVideoLibrary(db_path=str(tmp_path / "test.db"))
        assert lib.find_by_genre("nonexistent") == []
