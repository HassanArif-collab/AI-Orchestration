"""
visual/manifest.py — Tracks all visual assets for a video production.

Context: One video needs many assets — Remotion animations, Radiant shader
backgrounds, stock footage, screenshots, thumbnails. This manifest tracks
the planning and generation status of each asset.

Saved as JSON alongside the pipeline run data.

Imports: pydantic, pathlib, json
Imported by: packages/pipeline/handlers.py (visual_planning, asset_creation)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field


class AssetEntry(BaseModel):
    """One visual asset in the manifest."""
    asset_id: str
    asset_type: Literal[
        "remotion_animation", "radiant_shader",
        "stock_footage", "screenshot", "thumbnail"
    ]
    description: str
    source_tool: str   # "remotion", "radiant", "stock", "manual"
    status: Literal["planned", "generating", "complete", "failed"] = "planned"
    file_path: str | None = None
    error: str = ""
    spec: dict = {}


class AssetManifest(BaseModel):
    """Complete asset plan for one video."""
    video_title: str
    assets: list[AssetEntry] = Field(default_factory=list)

    def add_asset(self, entry: AssetEntry) -> None:
        """Add an asset entry to the manifest."""
        self.assets.append(entry)

    def get_pending(self) -> list[AssetEntry]:
        """Return all assets not yet complete or failed."""
        return [a for a in self.assets if a.status == "planned"]

    def get_by_type(self, asset_type: str) -> list[AssetEntry]:
        """Return all assets of a specific type."""
        return [a for a in self.assets if a.asset_type == asset_type]

    def mark_complete(self, asset_id: str, file_path: str) -> None:
        """Mark an asset as successfully generated."""
        for asset in self.assets:
            if asset.asset_id == asset_id:
                asset.status = "complete"
                asset.file_path = file_path
                return

    def mark_failed(self, asset_id: str, error: str) -> None:
        """Mark an asset as failed with error message."""
        for asset in self.assets:
            if asset.asset_id == asset_id:
                asset.status = "failed"
                asset.error = error
                return

    def summary(self) -> dict:
        """Return counts by status."""
        statuses = [a.status for a in self.assets]
        return {
            "total": len(self.assets),
            "planned": statuses.count("planned"),
            "generating": statuses.count("generating"),
            "complete": statuses.count("complete"),
            "failed": statuses.count("failed"),
        }

    def to_dict(self) -> dict:
        """Return JSON-serializable dict."""
        return self.model_dump()

    def save(self, filepath: str) -> None:
        """Save manifest as JSON."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_text(
            json.dumps(self.to_dict(), indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, filepath: str) -> AssetManifest:
        """Load manifest from JSON file."""
        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        return cls(**data)
