"""
FreeRouter — LiteLLM-based task router v4.0.

4 providers (Zhipu AI, Google AI Studio, Ollama Cloud, OpenRouter),
7 named routes with deep 6-level fallback chains.

v4.0 Changes:
  - Added Zhipu AI (glm-4-plus, glm-4-0520, glm-4-flash) as PRIMARY provider
  - Added Google AI Studio (gemini-2.0-flash) as secondary
  - Ollama Cloud as tertiary (weekly limits)
  - OpenRouter free models as last resort
  - 6-level fallback chains per route
  - Exponential backoff on rate limits (429)
"""

__version__ = "4.0.0"
__author__ = "FreeRouter"

from freerouter.config import ROUTES

# Pipeline task storage — kept for backward compatibility
from freerouter.storage import (
    create_pipeline_task,
    list_pipeline_tasks,
    get_pipeline_task,
    update_pipeline_task,
    delete_pipeline_task,
    add_task_thought,
)

__all__ = [
    "ROUTES",
    "__version__",
    "create_pipeline_task",
    "list_pipeline_tasks",
    "get_pipeline_task",
    "update_pipeline_task",
    "delete_pipeline_task",
    "add_task_thought",
]
