"""Notion API client for AI Orchestration system.

Provides methods for creating and managing script pages in Notion
with visual type color coding and formatting.
"""

from packages.core.config import get_settings
from packages.core.logger import get_logger
from packages.integrations.notion.colors import get_color, get_emoji

logger = get_logger(__name__)


class NotionScriptClient:
    """Client for Notion script page operations with graceful degradation.

    All methods return None/empty on failure, ensuring the pipeline
    never crashes due to Notion API issues.
    """

    def __init__(
        self,
        api_key: str | None = None,
        database_id: str | None = None,
    ) -> None:
        """Initialize the Notion client.

        Args:
            api_key: Optional Notion API key. Falls back to settings.NOTION_API_KEY.
            database_id: Optional database ID for script pages. Falls back to
                settings.NOTION_DATABASE_ID.
        """
        self.api_key = api_key or get_settings().NOTION_API_KEY
        self.database_id = database_id or get_settings().NOTION_DATABASE_ID
        self._client = None

        if self.api_key:
            try:
                from notion_client import Client

                self._client = Client(auth=self.api_key)
            except Exception as e:
                logger.warning(f"notion_init_failed: {e}")
                self._client = None
        else:
            logger.debug("Notion API key not configured, operating in degraded mode")

    def _check_client(self) -> bool:
        """Check if the Notion client is available.

        Returns:
            True if client is available, False otherwise.
        """
        if not self._client:
            logger.warning("notion_unavailable")
            return False
        return True

    def create_script_page(self, title: str, sections: list[dict]) -> str | None:
        """Create a Notion page for a video script.

        Creates a page with formatted sections, each containing:
        - Heading 2: section_type
        - Paragraph: narration text
        - Callout: visual_cue with color from get_color()

        Args:
            title: Title of the script/video.
            sections: List of section dictionaries with keys:
                - section_type: Type of section (intro, main, outro, etc.)
                - narration: The narration text
                - visual_cue: Optional visual cue description
                - visual_type: Optional visual type for coloring

        Returns:
            URL of the created page, or None on failure.
        """
        if not self._check_client():
            return None

        if not self.database_id:
            logger.warning("notion_no_database_id")
            return None

        try:
            # Build the page content
            children = []

            for section in sections:
                section_type = section.get("section_type", "Section")
                narration = section.get("narration", "")
                visual_cue = section.get("visual_cue", "")
                visual_type = section.get("visual_type", "")

                # Add section heading
                children.append({
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": section_type}}]
                    },
                })

                # Add narration paragraph
                if narration:
                    children.append({
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": narration}}]
                        },
                    })

                # Add visual cue as callout with color
                if visual_cue:
                    color = get_color(visual_type) if visual_type else "default"
                    emoji = get_emoji(visual_type) if visual_type else "🎬"

                    children.append({
                        "type": "callout",
                        "callout": {
                            "rich_text": [
                                {"type": "text", "text": {"content": visual_cue}}
                            ],
                            "icon": {"type": "emoji", "emoji": emoji},
                            "color": color,
                        },
                    })

            # Create the page
            response = self._client.pages.create(
                parent={"database_id": self.database_id},
                properties={
                    "title": {
                        "title": [{"type": "text", "text": {"content": title}}]
                    }
                },
                children=children,
            )

            page_id = response.get("id", "")
            page_url = response.get("url", "")

            logger.info(f"notion_page_created: title={title}, page_id={page_id}")

            return page_url

        except Exception as e:
            logger.warning(f"notion_error in create_script_page: {e}")
            return None

    def update_script_page(self, page_id: str, sections: list[dict]) -> None:
        """Update an existing Notion script page.

        Appends new sections to an existing page.

        Args:
            page_id: The Notion page ID.
            sections: List of section dictionaries to append.

        Note:
            Does nothing on failure - never crashes the pipeline.
        """
        if not self._check_client():
            return

        try:
            # Build the content blocks
            children = []

            for section in sections:
                section_type = section.get("section_type", "Section")
                narration = section.get("narration", "")
                visual_cue = section.get("visual_cue", "")
                visual_type = section.get("visual_type", "")

                # Add section heading
                children.append({
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": section_type}}]
                    },
                })

                # Add narration paragraph
                if narration:
                    children.append({
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": narration}}]
                        },
                    })

                # Add visual cue as callout
                if visual_cue:
                    color = get_color(visual_type) if visual_type else "default"
                    emoji = get_emoji(visual_type) if visual_type else "🎬"

                    children.append({
                        "type": "callout",
                        "callout": {
                            "rich_text": [
                                {"type": "text", "text": {"content": visual_cue}}
                            ],
                            "icon": {"type": "emoji", "emoji": emoji},
                            "color": color,
                        },
                    })

            # Append blocks to the page
            if children:
                self._client.blocks.children.append(
                    block_id=page_id,
                    children=children,
                )

            logger.info(f"notion_page_updated: page_id={page_id}")

        except Exception as e:
            logger.warning(f"notion_error in update_script_page: {e}")

    def get_script(self, page_id: str) -> dict:
        """Retrieve a script page from Notion.

        Args:
            page_id: The Notion page ID.

        Returns:
            Dictionary containing page content, or empty dict on failure.
        """
        if not self._check_client():
            return {}

        try:
            # Get page properties
            page = self._client.pages.retrieve(page_id=page_id)

            # Get page content blocks
            blocks = self._client.blocks.children.list(block_id=page_id)

            result = {
                "page_id": page_id,
                "title": "",
                "sections": [],
                "url": page.get("url", ""),
            }

            # Extract title
            title_prop = page.get("properties", {}).get("title", {})
            if title_prop.get("title"):
                result["title"] = title_prop["title"][0].get("text", {}).get("content", "")

            # Parse blocks into sections
            current_section = None

            for block in blocks.get("results", []):
                block_type = block.get("type", "")

                if block_type == "heading_2":
                    if current_section:
                        result["sections"].append(current_section)
                    current_section = {
                        "section_type": self._extract_text(block, "heading_2"),
                        "narration": "",
                        "visual_cue": "",
                        "visual_type": "",
                    }
                elif block_type == "paragraph" and current_section:
                    current_section["narration"] = self._extract_text(block, "paragraph")
                elif block_type == "callout" and current_section:
                    current_section["visual_cue"] = self._extract_text(block, "callout")
                    # Try to infer visual type from color
                    color = block.get("callout", {}).get("color", "default")
                    for vtype, vcolor in {
                        "talking_head": "red",
                        "animation": "blue",
                        "broll": "green",
                        "screen_recording": "yellow",
                        "data_viz": "purple",
                        "shader_bg": "gray",
                    }.items():
                        if vcolor == color:
                            current_section["visual_type"] = vtype
                            break

            if current_section:
                result["sections"].append(current_section)

            return result

        except Exception as e:
            logger.warning(f"notion_error in get_script: {e}")
            return {}

    def _extract_text(self, block: dict, block_type: str) -> str:
        """Extract plain text from a Notion block.

        Args:
            block: The Notion block object.
            block_type: The type of the block.

        Returns:
            Extracted text or empty string.
        """
        try:
            rich_text = block.get(block_type, {}).get("rich_text", [])
            texts = [t.get("text", {}).get("content", "") for t in rich_text]
            return "".join(texts)
        except Exception:
            return ""
