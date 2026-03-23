"""
radiant/embedder.py — Embed Radiant shaders as HTML/TSX backgrounds.

Context: Generates code to use Radiant shaders as animated video backgrounds.
Three output formats:
  1. iframe HTML — embed in any webpage
  2. Full overlay HTML — shader bg + text overlay (for screenshots/frames)
  3. Remotion TSX — embed in Remotion compositions for video rendering

6 color schemes via CSS filters (from Radiant docs):
  amber, mono, blue, rose, emerald, arctic

Pure functions — no external calls, always safe to call.

Imports: nothing external
Imported by: packages/pipeline/handlers.py (visual_planning stage)
"""

from __future__ import annotations

COLOR_SCHEMES: dict[str, str] = {
    "amber":   "none",
    "mono":    "grayscale(1)",
    "blue":    "hue-rotate(175deg)",
    "rose":    "hue-rotate(300deg) saturate(1.1)",
    "emerald": "hue-rotate(90deg) saturate(1.2)",
    "arctic":  "hue-rotate(180deg) saturate(0.5) brightness(1.1)",
}


def generate_iframe_embed(
    shader_name: str,
    color_scheme: str = "amber",
    shader_dir: str = "data/radiant-shaders",
) -> str:
    """Generate HTML iframe code for embedding a shader as background."""
    css_filter = COLOR_SCHEMES.get(color_scheme, "none")
    filter_style = f"filter: {css_filter};" if css_filter != "none" else ""
    return (
        f'<iframe src="{shader_dir}/static/{shader_name}.html" '
        f'style="position:absolute;top:0;left:0;width:100%;height:100%;'
        f'border:none;pointer-events:none;{filter_style}" '
        f'title="Background: {shader_name}"></iframe>'
    )


def generate_overlay_html(
    shader_name: str,
    text: str,
    text_style: dict | None = None,
    color_scheme: str = "amber",
    shader_dir: str = "data/radiant-shaders",
) -> str:
    """Generate full HTML page: shader background + text overlay.

    This page can be screenshot'd for video frames or thumbnails.
    """
    style = text_style or {}
    font = style.get("font", "Inter, sans-serif")
    size = style.get("size", "48px")
    color = style.get("color", "white")
    position = style.get("position", "center")

    align_map = {
        "center": "center", "top": "flex-start",
        "bottom": "flex-end", "left": "flex-start", "right": "flex-end"
    }
    justify = align_map.get(position, "center")
    align_items = "center" if position in ("center", "left", "right") else align_map.get(position, "center")

    iframe = generate_iframe_embed(shader_name, color_scheme, shader_dir)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ margin: 0; padding: 0; width: 1920px; height: 1080px;
          overflow: hidden; position: relative; }}
  .overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%;
              display: flex; align-items: {align_items};
              justify-content: {justify}; z-index: 10; padding: 80px;
              box-sizing: border-box; }}
  .text {{ font-family: {font}; font-size: {size}; color: {color};
           text-align: {position if position in ('center','left','right') else 'center'};
           text-shadow: 0 2px 20px rgba(0,0,0,0.8); max-width: 1400px;
           line-height: 1.3; }}
</style>
</head>
<body>
{iframe}
<div class="overlay"><div class="text">{text}</div></div>
</body>
</html>"""


def generate_remotion_background(
    shader_name: str,
    color_scheme: str = "amber",
    shader_dir: str = "data/radiant-shaders",
) -> str:
    """Generate TSX code embedding a Radiant shader as Remotion background."""
    css_filter = COLOR_SCHEMES.get(color_scheme, "none")
    filter_style = f"filter: '{css_filter}'" if css_filter != "none" else ""

    return f"""import {{AbsoluteFill}} from 'remotion';

export const {shader_name.replace('-', '')}Background: React.FC = () => {{
  return (
    <AbsoluteFill>
      <iframe
        src="{shader_dir}/static/{shader_name}.html"
        style={{{{
          position: 'absolute', top: 0, left: 0,
          width: '100%', height: '100%',
          border: 'none', pointerEvents: 'none',
          {filter_style}
        }}}}
      />
    </AbsoluteFill>
  );
}};"""
