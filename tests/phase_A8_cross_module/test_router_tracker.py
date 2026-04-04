"""Tests for packages/router/tracker.py — Token/cost tracking."""

import pytest
from datetime import date, timezone
from pathlib import Path


class TestUsageTrackerInit:
    """Tests for UsageTracker initialization."""

    def test_init_creates_db(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker(db_path=Path(tmp_db_path))
        assert tracker.db_path == Path(tmp_db_path)

    def test_init_creates_db_directory(self, tmp_path):
        from packages.router.tracker import UsageTracker
        nested = tmp_path / "sub" / "dir" / "pipeline.db"
        tracker = UsageTracker(db_path=nested)
        assert nested.parent.exists()


class TestRecordCall:
    """Tests for UsageTracker.record_call()."""

    @pytest.fixture()
    def tracker(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        return UsageTracker(db_path=Path(tmp_db_path))

    def test_record_successful_call(self, tracker):
        tracker.record_call("groq", "llama-3.3-70b", 100, 200, 450, True)
        usage = tracker.get_daily_usage("groq")
        assert usage["requests"] == 1
        assert usage["total_tokens"] == 300

    def test_record_failed_call_not_counted(self, tracker):
        tracker.record_call("groq", "llama-3.3-70b", 100, 200, 450, False)
        usage = tracker.get_daily_usage("groq")
        assert usage["requests"] == 0
        assert usage["total_tokens"] == 0

    def test_record_with_rate_limits(self, tracker):
        tracker.record_call("groq", "llama-3.3-70b", 50, 150, 300, True,
                            rpm_remaining=500, tpm_remaining=10000)
        limits = tracker.get_latest_limits()
        assert len(limits) == 1
        assert limits[0]["live_rpm_remaining"] == 500
        assert limits[0]["live_tpm_remaining"] == 10000

    def test_record_multiple_calls(self, tracker):
        for i in range(5):
            tracker.record_call("groq", "llama-3.3-70b", 100, 200, 100, True)
        usage = tracker.get_daily_usage("groq")
        assert usage["requests"] == 5
        assert usage["total_tokens"] == 1500


class TestGetDailyUsage:
    """Tests for UsageTracker.get_daily_usage()."""

    @pytest.fixture()
    def tracker(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        return UsageTracker(db_path=Path(tmp_db_path))

    def test_empty_provider(self, tracker):
        usage = tracker.get_daily_usage("nonexistent")
        assert usage["requests"] == 0
        assert usage["total_tokens"] == 0
        assert usage["avg_latency_ms"] == 0

    def test_returns_provider_name(self, tracker):
        tracker.record_call("ollama", "llama3.2", 50, 100, 200, True)
        usage = tracker.get_daily_usage("ollama")
        assert usage["provider"] == "ollama"

    def test_returns_today_date(self, tracker):
        tracker.record_call("groq", "llama-3.3-70b", 50, 100, 200, True)
        usage = tracker.get_daily_usage("groq")
        assert usage["date"] == date.today().isoformat()

    def test_avg_latency(self, tracker):
        tracker.record_call("groq", "llama-3.3-70b", 50, 100, 200, True)
        tracker.record_call("groq", "llama-3.3-70b", 50, 100, 400, True)
        usage = tracker.get_daily_usage("groq")
        assert usage["avg_latency_ms"] == 300


class TestGetAllUsageToday:
    """Tests for UsageTracker.get_all_usage_today()."""

    def test_returns_all_providers(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker(db_path=Path(tmp_db_path))
        tracker.record_call("groq", "llama-3.3-70b", 100, 200, 100, True)
        tracker.record_call("ollama", "llama3.2", 50, 100, 200, True)
        result = tracker.get_all_usage_today()
        assert len(result) == 2
        providers = {r["provider"] for r in result}
        assert providers == {"groq", "ollama"}

    def test_empty_database(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker(db_path=Path(tmp_db_path))
        result = tracker.get_all_usage_today()
        assert result == []


class TestGetLatestLimits:
    """Tests for UsageTracker.get_latest_limits()."""

    def test_empty_database(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker(db_path=Path(tmp_db_path))
        result = tracker.get_latest_limits()
        assert result == []

    def test_returns_latest_per_provider(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker(db_path=Path(tmp_db_path))
        tracker.record_call("groq", "llama-3.3-70b", 50, 100, 200, True,
                            rpm_remaining=100, tpm_remaining=5000)
        tracker.record_call("groq", "llama-3.3-70b", 50, 100, 300, True,
                            rpm_remaining=80, tpm_remaining=4000)
        result = tracker.get_latest_limits()
        assert len(result) == 1
        assert result[0]["live_rpm_remaining"] == 80


class TestIsNearLimit:
    """Tests for UsageTracker.is_near_limit()."""

    def test_no_data_returns_false(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker(db_path=Path(tmp_db_path))
        assert tracker.is_near_limit("groq") is False

    def test_near_limit_when_rpm_low(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker(db_path=Path(tmp_db_path))
        tracker.record_call("groq", "llama-3.3-70b", 50, 100, 200, True,
                            rpm_remaining=50, tpm_remaining=50000)
        assert tracker.is_near_limit("groq") is True

    def test_near_limit_when_tpm_low(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker(db_path=Path(tmp_db_path))
        tracker.record_call("groq", "llama-3.3-70b", 50, 100, 200, True,
                            rpm_remaining=500, tpm_remaining=5000)
        assert tracker.is_near_limit("groq") is True

    def test_not_near_limit_with_good_headers(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker(db_path=Path(tmp_db_path))
        tracker.record_call("groq", "llama-3.3-70b", 50, 100, 200, True,
                            rpm_remaining=500, tpm_remaining=50000)
        assert tracker.is_near_limit("groq") is False

    def test_ollama_always_not_near_limit(self, tmp_db_path):
        from packages.router.tracker import UsageTracker
        tracker = UsageTracker(db_path=Path(tmp_db_path))
        # Ollama returns -1 for both (unlimited)
        tracker.record_call("ollama", "llama3.2", 50, 100, 200, True,
                            rpm_remaining=-1, tpm_remaining=-1)
        assert tracker.is_near_limit("ollama") is False


class TestConstants:
    """Tests for module constants."""

    def test_near_limit_threshold(self):
        from packages.router.tracker import NEAR_LIMIT_THRESHOLD
        assert NEAR_LIMIT_THRESHOLD == 0.80
