"""
FreeRouter — LiteLLM-based task router v3.1.

2 providers (OpenRouter, Ollama Cloud), 7 named routes with
multi-fallback chains. Delegates provider management to LiteLLM.
Keeps only the task-based routing logic and pipeline task storage.

v3.1 Changes:
  - Removed Groq as a provider
  - 2 providers remaining: OpenRouter (primary) + Ollama Cloud (creative)
  - Multi-fallback chains: primary → fallback → fallback2
  - StepFun 3.5 Flash as primary for auto/scorer
"""

__version__ = "3.1.0"
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
