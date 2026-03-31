"""visual_routes.py — Radiant shaders, Remotion templates, asset manifests."""
from __future__ import annotations
import glob, os, re
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from apps.api.dependencies import get_radiant_manager

router = APIRouter()

# Base directory for shader files — resolved once at module load
SHADER_BASE_DIR = Path("data/radiant-shaders/static").resolve()

@router.get("/manifests")
async def list_manifests():
    manifests = []
    for f in glob.glob("packages/data/*.manifest.json"):
        try:
            from packages.visual.manifest import AssetManifest
            m = AssetManifest.load(f)
            s = m.summary()
            manifests.append({"video_title": m.video_title, **s, "filepath": f})
        except Exception:
            pass
    return manifests

@router.get("/radiant/shaders")
async def list_shaders():
    mgr = get_radiant_manager()
    if not mgr:
        return []
    shaders = mgr.list_shaders()
    if not shaders:
        return []
    return [{"name": s["name"], "path": s["path"], "tags": []} for s in shaders]

@router.get("/radiant/preview/{shader_name}")
async def preview_shader(shader_name: str):
    # C1 FIX: Block any path separator or traversal attempt
    if not re.match(r'^[a-zA-Z0-9_\-]+$', shader_name):
        raise HTTPException(400, "Invalid shader name")

    shader_path = (SHADER_BASE_DIR / f"{shader_name}.html").resolve()

    # Double-check resolved path stays within base directory
    if not str(shader_path).startswith(str(SHADER_BASE_DIR)):
        raise HTTPException(403, "Access denied")

    if shader_path.exists():
        return FileResponse(shader_path, media_type="text/html")
    raise HTTPException(404, f"Shader '{shader_name}' not found. Run RadiantManager().setup() first.")

@router.get("/radiant/moods")
async def list_mood_mappings():
    try:
        from packages.visual.radiant.manager import MOOD_TO_SHADER
        return MOOD_TO_SHADER
    except ImportError:
        return {}

@router.get("/remotion/compositions")
async def list_compositions():
    if not os.path.exists("visual-engine"):
        return {"error": "Remotion project not scaffolded",
                "help": "from packages.visual.remotion.setup import scaffold_project; scaffold_project()"}
    tsx_files = glob.glob("visual-engine/src/compositions/*.tsx")
    return [{"name": os.path.splitext(os.path.basename(f))[0]} for f in tsx_files]

@router.get("/remotion/templates")
async def list_templates():
    return ["bar_chart", "line_chart", "text_reveal", "counter",
            "comparison", "timeline", "map_highlight"]
