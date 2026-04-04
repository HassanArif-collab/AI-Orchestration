"""
FreeRouter — LiteLLM-based task router v3.

Slimmed-down version that delegates provider management to LiteLLM.
Keeps only the task-based routing logic and pipeline task storage.

v3 Migration: providers.py, router.py, circuit_breaker.py, rate_limit_store.py,
cli.py, proxy_server.py, exceptions.py, adapters/ all deleted.
Only config.py, server.py, and storage.py remain.
"""

__version__ = "3.0.0"
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
