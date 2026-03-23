"""Stage 1: YouTube Source Extraction.

Accepts a YouTube URL and extracts everything needed for structural analysis.
Purely data collection — no interpretation happens here.
"""

import re
import uuid
from urllib.parse import parse_qs, urlparse

from packages.core.logger import get_logger
from packages.integrations.youtube.client import YouTubeClient

from ..error_log import ErrorLogger
from ..models import (
    ChapterMarker,
    ProcessingStatus,
    RawExtraction,
    SourceVideoRecord,
    TranscriptSegment,
)
from ..source_library import SourceVideoLibrary

logger = get_logger(__name__)


def parse_video_id(url_or_id: str) -> str:
    """Extract YouTube video ID from a URL or return as-is if already an ID.

    Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - Plain VIDEO_ID
    """
    if len(url_or_id) == 11 and not url_or_id.startswith("http"):
        return url_or_id

    parsed = urlparse(url_or_id)

    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            return qs.get("v", [""])[0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[1].split("?")[0]
    elif parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/").split("?")[0]

    # Fallback: assume it's a video ID
    return url_or_id


def parse_iso_duration(iso_duration: str) -> float:
    """Convert ISO 8601 duration (PT1H2M3S) to seconds."""
    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, iso_duration)
    if not match:
        return 0.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def extract_chapters(description: str) -> list[ChapterMarker]:
    """Extract chapter markers from a YouTube video description.

    Looks for lines like:
        0:00 Introduction
        1:23 First Topic
        01:02:30 Long Chapter
    """
    pattern = r"(?:^|\n)\s*(\d{1,2}:)?(\d{1,2}):(\d{2})\s+(.+)"
    matches = re.findall(pattern, description)

    chapters = []
    for hours_part, minutes, seconds, title in matches:
        hours = int(hours_part.rstrip(":")) if hours_part else 0
        total_seconds = hours * 3600 + int(minutes) * 60 + int(seconds)
        chapters.append(
            ChapterMarker(
                title=title.strip(),
                start_seconds=float(total_seconds),
            )
        )

    return chapters


async def stage1_extract(
    url_or_id: str,
    youtube_client: YouTubeClient | None = None,
    source_library: SourceVideoLibrary | None = None,
    error_logger: ErrorLogger | None = None,
    cycle_id: str | None = None,
) -> RawExtraction | None:
    """Stage 1: Extract everything from a YouTube video.

    Args:
        url_or_id: YouTube URL or video ID.
        youtube_client: Existing client instance (creates one if not provided).
        source_library: Source Video Library for caching.
        error_logger: Error logger for pipeline errors.
        cycle_id: Production cycle ID for error logging.

    Returns:
        RawExtraction on success, None on failure.
    """
    cycle_id = cycle_id or str(uuid.uuid4())
    client = youtube_client or YouTubeClient()
    library = source_library or SourceVideoLibrary()
    errors = error_logger or ErrorLogger()

    video_id = parse_video_id(url_or_id)
    url = f"https://www.youtube.com/watch?v={video_id}"

    # Check cache first
    if library.exists(video_id):
        logger.info(f"stage1_cache_hit: {video_id}")
        record = library.load(video_id)
        if record and record.extraction:
            return record.extraction

    # Get video metadata
    details = client.get_video_details(video_id)
    if not details:
        errors.log_error(
            cycle_id, 1, "Video Inaccessible",
            f"Could not retrieve video details for {video_id}",
            content_element=video_id,
        )
        return None

    # Get transcript
    transcript_data = client.get_transcript(video_id)
    if not transcript_data or not transcript_data.get("segments"):
        errors.log_error(
            cycle_id, 1, "Caption Unavailable",
            f"No captions available for {video_id}",
            content_element=video_id,
        )
        return None

    # Build transcript segments
    segments = [
        TranscriptSegment(
            text=seg["text"],
            start=seg["start"],
            duration=seg["duration"],
        )
        for seg in transcript_data["segments"]
    ]

    # Extract chapters from description
    chapters = extract_chapters(details.get("description", ""))

    # Parse duration
    duration_seconds = parse_iso_duration(details.get("duration", ""))

    # Build extraction
    extraction = RawExtraction(
        video_id=video_id,
        url=url,
        title=details.get("title", ""),
        description=details.get("description", ""),
        channel_id=details.get("channel_id", ""),
        channel_title=details.get("channel_title", ""),
        published_at=details.get("published_at", ""),
        duration_iso=details.get("duration", ""),
        duration_seconds=duration_seconds,
        views=details.get("views", 0),
        likes=details.get("likes", 0),
        comments=details.get("comments", 0),
        tags=details.get("tags", []),
        thumbnail_url=details.get("thumbnail_url", ""),
        transcript_segments=segments,
        caption_type=transcript_data.get("caption_type", "unknown"),
        transcript_language=transcript_data.get("language", "en"),
        word_count=transcript_data.get("word_count", 0),
        chapters=chapters,
    )

    # Check minimum transcript length
    if extraction.word_count < 2000:
        errors.log_warning(
            cycle_id, 1, "Short Transcript",
            f"Transcript is {extraction.word_count} words (minimum 2000). "
            "Output flagged for human review.",
            content_element=video_id,
        )

    # Save to Source Video Library
    record = SourceVideoRecord(
        video_id=video_id,
        url=url,
        title=extraction.title,
        published_at=extraction.published_at,
        views=extraction.views,
        likes=extraction.likes,
        extraction=extraction,
        processing_status=ProcessingStatus.EXTRACTED_ONLY,
    )
    library.save(record)

    logger.info(
        f"stage1_complete: {video_id} — {extraction.word_count} words, "
        f"{len(chapters)} chapters, caption_type={extraction.caption_type}"
    )

    return extraction
