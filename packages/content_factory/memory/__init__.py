"""
Content Factory Memory — Zep Integration Layer.

Provides ZepAudienceModelStore for writing and reading audience intelligence.
All operations are guarded by ZEP_ENABLED flag in config.
Set ZEP_ENABLED=true in .env once your ZEP_API_KEY is confirmed working.
"""

from .zep_store import ZepAudienceModelStore

__all__ = ["ZepAudienceModelStore"]
