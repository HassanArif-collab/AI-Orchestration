"""JSON extraction utilities for safely parsing LLM output.

Replaces the greedy regex pattern ``re.search(r'\\{.*\\}', text, re.DOTALL)``
with a balanced-brace counting algorithm that correctly handles:
- Nested JSON objects/arrays
- Curly braces inside quoted strings
- Escaped characters within strings
- LLM output with explanatory text before/after JSON
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _find_balanced(text: str, open_char: str, close_char: str) -> Optional[str]:
    """Extract content between balanced open_char and close_char.

    Walks character-by-character, tracking nesting depth and
    whether we're inside a quoted string. Returns the substring
    including the outer delimiters, or None if no balanced pair found.

    This is immune to the greedy-matching problem that plagues
    regex patterns like ``r'\\{.*\\}'`` with re.DOTALL.
    """
    depth = 0
    in_string = False
    escape_next = False
    start = -1

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue

        if ch == '\\' and in_string:
            escape_next = True
            continue

        if ch == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == open_char:
            if depth == 0:
                start = i
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start:i + 1]
                # Verify it's valid JSON by attempting to parse
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    # Not valid JSON; keep looking for another balanced pair
                    start = -1
                    depth = 0

    return None


def extract_json_object(text: str) -> Optional[str]:
    """Extract the first valid JSON object {...} from text.

    Args:
        text: Raw text (typically LLM output) that may contain JSON.

    Returns:
        The JSON string (including outer braces) if found, None otherwise.
    """
    return _find_balanced(text, '{', '}')


def extract_json_array(text: str) -> Optional[str]:
    """Extract the first valid JSON array [...] from text.

    Args:
        text: Raw text (typically LLM output) that may contain JSON.

    Returns:
        The JSON string (including outer brackets) if found, None otherwise.
    """
    return _find_balanced(text, '[', ']')
