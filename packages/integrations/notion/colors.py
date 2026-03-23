"""Visual type color mappings for Notion script pages.

Maps visual types used in video scripts to Notion color values and emojis
for consistent visual representation in Notion pages.
"""

# Color mappings for visual types in Notion
VISUAL_TYPE_COLORS: dict[str, str] = {
    "talking_head": "red",
    "animation": "blue",
    "broll": "green",
    "screen_recording": "yellow",
    "data_viz": "purple",
    "shader_bg": "gray",
}

# Emoji mappings for visual types
EMOJI_MAP: dict[str, str] = {
    "talking_head": "🔴",
    "animation": "🔵",
    "broll": "🟢",
    "screen_recording": "🟡",
    "data_viz": "🟣",
    "shader_bg": "⚫",
}


def get_color(visual_type: str) -> str:
    """Get the Notion color for a visual type.

    Args:
        visual_type: The visual type name.

    Returns:
        Notion color string (e.g., "red", "blue") or "default" if not found.
    """
    return VISUAL_TYPE_COLORS.get(visual_type, "default")


def get_emoji(visual_type: str) -> str:
    """Get the emoji for a visual type.

    Args:
        visual_type: The visual type name.

    Returns:
        Emoji string or a default white square if not found.
    """
    return EMOJI_MAP.get(visual_type, "⬜")
