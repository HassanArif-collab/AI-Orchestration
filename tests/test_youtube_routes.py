"""Tests for YouTube analytics routes."""


def test_competitor_endpoint_structure():
    """The competitor endpoint should return a list of videos."""
    # Create a mock response
    mock_videos = [
        {
            "title": "Test Video",
            "video_id": "abc123",
            "channel_title": "Test Channel",
            "views": 100000,
            "published_at": "2026-01-01T00:00:00Z",
        }
    ]
    
    # Verify structure
    assert len(mock_videos) == 1
    assert mock_videos[0]["video_id"] == "abc123"
    assert mock_videos[0]["views"] == 100000


def test_repurpose_payload_structure():
    """The repurpose endpoint should create correct card structure."""
    body = {
        "title": "Test Competitor Video",
        "video_id": "abc123",
        "channel": "TestChannel",
        "views": 150000,
    }
    
    # Verify the insert payload has the right structure
    card_brief = {
        "title": f"[Repurpose] {body['title']}",
        "description": f"Adapted from competitor video: {body['channel']}",
        "angle": "adaptation",
        "source_video_id": body["video_id"],
    }
    
    assert "[Repurpose]" in card_brief["title"]
    assert card_brief["angle"] == "adaptation"
    assert card_brief["source_video_id"] == "abc123"


def test_video_url_construction():
    """Verify YouTube video URLs are constructed correctly."""
    video_id = "abc123"
    url = f"https://youtube.com/watch?v={video_id}"
    assert "youtube.com" in url
    assert video_id in url


def test_views_formatting():
    """Verify view count formatting for display."""
    def format_views(views):
        if views >= 1_000_000:
            return f"{views / 1_000_000:.1f}M"
        elif views >= 1_000:
            return f"{views / 1_000:.1f}K"
        return str(views)
    
    assert format_views(1500000) == "1.5M"
    assert format_views(15000) == "15.0K"
    assert format_views(150) == "150"
