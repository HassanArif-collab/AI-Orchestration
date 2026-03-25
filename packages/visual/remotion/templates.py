"""
remotion/templates.py — Generate TypeScript/React code for Remotion animations.

Context: Remotion renders React components to video. We generate .tsx files
that Remotion can compile and render without manual coding.

7 animation types supported:
  bar_chart    — animated bars from 0 to value
  line_chart   — SVG path drawing itself
  text_reveal  — words appear one at a time
  counter      — number counts up to target
  comparison   — two items side by side
  timeline     — horizontal timeline with events
  map_highlight— CSS region highlight card

All generated code uses only: useCurrentFrame, interpolate, AbsoluteFill
from 'remotion'. No external libraries in generated code.

Imports: pydantic
Imported by: packages/visual/remotion/renderer.py
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class AnimationSpec(BaseModel):
    """Specification for one Remotion animation composition."""
    type: Literal[
        "bar_chart", "line_chart", "text_reveal",
        "counter", "comparison", "timeline", "map_highlight"
    ]
    title: str
    data: dict
    duration_frames: int = 150   # 5 seconds at 30fps
    width: int = 1920
    height: int = 1080
    fps: int = 30
    colors: dict = Field(default_factory=lambda: {
        "primary": "#FF6B6B",
        "secondary": "#4ECDC4",
        "background": "#1A1A2E",
        "text": "#FFFFFF",
    })

    @property
    def component_name(self) -> str:
        """PascalCase component name derived from title."""
        return "".join(w.capitalize() for w in self.title.split())


def generate_composition(spec: AnimationSpec) -> str:
    """Generate valid TypeScript/React code for a Remotion composition."""
    bg = spec.colors.get("background", "#1A1A2E")
    text = spec.colors.get("text", "#FFFFFF")
    primary = spec.colors.get("primary", "#FF6B6B")
    name = spec.component_name

    if spec.type == "counter":
        target = spec.data.get("target", 1000)
        prefix = spec.data.get("prefix", "")
        suffix = spec.data.get("suffix", "")
        return f"""import {{useCurrentFrame, interpolate, AbsoluteFill}} from 'remotion';

export const {name}: React.FC = () => {{
  const frame = useCurrentFrame();
  const value = interpolate(frame, [0, {spec.duration_frames}], [0, {target}],
    {{extrapolateRight: 'clamp'}});
  return (
    <AbsoluteFill style={{{{background: '{bg}', display: 'flex',
      alignItems: 'center', justifyContent: 'center'}}}}>
      <span style={{{{fontSize: 120, color: '{text}', fontFamily: 'Inter',
        fontWeight: 'bold'}}}}>
        {prefix}{{Math.floor(value).toLocaleString()}}{suffix}
      </span>
    </AbsoluteFill>
  );
}};"""

    if spec.type == "text_reveal":
        text_content = spec.data.get("text", "")
        words = text_content.split()
        words_per_frame = max(1, len(words) / spec.duration_frames)
        return f"""import {{useCurrentFrame, interpolate, AbsoluteFill}} from 'remotion';

const WORDS = {words};

export const {name}: React.FC = () => {{
  const frame = useCurrentFrame();
  const visibleCount = Math.floor(frame * {words_per_frame:.3f}) + 1;
  return (
    <AbsoluteFill style={{{{background: '{bg}', display: 'flex',
      alignItems: 'center', justifyContent: 'center', padding: 80}}}}>
      <p style={{{{fontSize: 64, color: '{text}', fontFamily: 'Inter',
        lineHeight: 1.4, textAlign: 'center'}}}}>
        {{WORDS.slice(0, visibleCount).join(' ')}}
      </p>
    </AbsoluteFill>
  );
}};"""

    if spec.type == "bar_chart":
        labels = spec.data.get("labels", ["A", "B", "C"])
        values = spec.data.get("values", [100, 200, 150])
        max_val = max(values) if values else 1
        return f"""import {{useCurrentFrame, interpolate, AbsoluteFill}} from 'remotion';

const DATA = {list(zip(labels, values))};
const MAX = {max_val};

export const {name}: React.FC = () => {{
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [0, {spec.duration_frames}], [0, 1],
    {{extrapolateRight: 'clamp'}});
  return (
    <AbsoluteFill style={{{{background: '{bg}', display: 'flex',
      alignItems: 'flex-end', justifyContent: 'center',
      gap: 20, paddingBottom: 80}}}}>
      {{DATA.map(([label, value], i) => (
        <div key={{i}} style={{{{display: 'flex', flexDirection: 'column',
          alignItems: 'center', gap: 8}}}}>
          <div style={{{{width: 80,
            height: `${{(value / MAX) * 400 * progress}}px`,
            background: '{primary}', borderRadius: 4}}}}/>
          <span style={{{{color: '{text}', fontSize: 18}}}}>{{label}}</span>
          <span style={{{{color: '{text}', fontSize: 14, opacity: 0.7}}}}>{{value}}</span>
        </div>
      ))}}
    </AbsoluteFill>
  );
}};"""

    if spec.type == "comparison":
        left = spec.data.get("left", {"label": "Option A", "value": "50%"})
        right = spec.data.get("right", {"label": "Option B", "value": "50%"})
        return f"""import {{useCurrentFrame, interpolate, AbsoluteFill}} from 'remotion';

export const {name}: React.FC = () => {{
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 30], [0, 1],
    {{extrapolateRight: 'clamp'}});
  return (
    <AbsoluteFill style={{{{background: '{bg}', display: 'flex',
      alignItems: 'center', justifyContent: 'center', gap: 60, opacity}}}}>
      <div style={{{{textAlign: 'center', color: '{text}'}}}}>
        <div style={{{{fontSize: 80, fontWeight: 'bold'}}}}>{left.get('value')}</div>
        <div style={{{{fontSize: 32, opacity: 0.7}}}}>{left.get('label')}</div>
      </div>
      <div style={{{{fontSize: 48, color: '{primary}', opacity: 0.5}}}}>VS</div>
      <div style={{{{textAlign: 'center', color: '{text}'}}}}>
        <div style={{{{fontSize: 80, fontWeight: 'bold'}}}}>{right.get('value')}</div>
        <div style={{{{fontSize: 32, opacity: 0.7}}}}>{right.get('label')}</div>
      </div>
    </AbsoluteFill>
  );
}};"""

    if spec.type == "timeline":
        events = spec.data.get("events", [{"year": 2020, "label": "Event"}])
        return f"""import {{useCurrentFrame, interpolate, AbsoluteFill}} from 'remotion';

const EVENTS = {events};

export const {name}: React.FC = () => {{
  const frame = useCurrentFrame();
  const visible = Math.floor(interpolate(frame,
    [0, {spec.duration_frames}], [0, EVENTS.length],
    {{extrapolateRight: 'clamp'}}));
  return (
    <AbsoluteFill style={{{{background: '{bg}', display: 'flex',
      flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: 24}}}}>
      {{EVENTS.slice(0, visible + 1).map((e, i) => (
        <div key={{i}} style={{{{display: 'flex', alignItems: 'center',
          gap: 16, color: '{text}'}}}}>
          <span style={{{{fontSize: 28, fontWeight: 'bold',
            color: '{primary}'}}}}>{{}}</span>
          <span style={{{{fontSize: 24}}}}>{{}}</span>
        </div>
      ))}}
    </AbsoluteFill>
  );
}};"""

    if spec.type == "map_highlight":
        region = spec.data.get("region", "Pakistan")
        highlight = spec.data.get("highlight_color", "#FF6B6B")
        return f"""import {{useCurrentFrame, interpolate, AbsoluteFill}} from 'remotion';

export const {name}: React.FC = () => {{
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, 20], [0.8, 1],
    {{extrapolateRight: 'clamp'}});
  const opacity = interpolate(frame, [0, 20], [0, 1],
    {{extrapolateRight: 'clamp'}});
  return (
    <AbsoluteFill style={{{{background: '{bg}', display: 'flex',
      alignItems: 'center', justifyContent: 'center', opacity}}}}>
      <div style={{{{transform: `scale(${{scale}})`, textAlign: 'center'}}}}>
        <div style={{{{fontSize: 48, color: '{text}', marginBottom: 16}}}}>
          {region}
        </div>
        <div style={{{{width: 200, height: 200, background: '{highlight}',
          borderRadius: 8, margin: '0 auto', opacity: 0.8}}}}/>
      </div>
    </AbsoluteFill>
  );
}};"""

    # Default: line_chart
    points = spec.data.get("points", [[0, 0], [1, 50], [2, 100]])
    return f"""import {{useCurrentFrame, interpolate, AbsoluteFill}} from 'remotion';

const POINTS = {points};

export const {name}: React.FC = () => {{
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [0, {spec.duration_frames}], [0, 1],
    {{extrapolateRight: 'clamp'}});
  const visiblePoints = POINTS.slice(0,
    Math.max(2, Math.floor(POINTS.length * progress)));
  const pathD = visiblePoints.map((p, i) =>
    `${{i === 0 ? 'M' : 'L'}} ${{p[0] * 100 + 100}} ${{500 - p[1] * 4}}`
  ).join(' ');
  return (
    <AbsoluteFill style={{{{background: '{bg}'}}}}>
      <svg width="100%" height="100%" viewBox="0 0 1920 1080">
        <path d={{pathD}} stroke="{primary}" strokeWidth="4"
          fill="none" strokeLinecap="round"/>
      </svg>
    </AbsoluteFill>
  );
}};"""


def generate_root_file(compositions: list[AnimationSpec]) -> str:
    """Generate Root.tsx that registers all compositions with Remotion."""
    imports = "\n".join(
        f"import {{{spec.component_name}}} from './compositions/{spec.component_name}';"
        for spec in compositions
    )
    registrations = "\n".join(
        f"""  <Composition id="{spec.component_name}"
    component={{{spec.component_name}}}
    durationInFrames={{{spec.duration_frames}}}
    fps={{{spec.fps}}}
    width={{{spec.width}}}
    height={{{spec.height}}}
  />"""
        for spec in compositions
    )
    return f"""import {{Composition}} from 'remotion';
{imports}

export const RemotionRoot: React.FC = () => {{
  return (
    <>
{registrations}
    </>
  );
}};"""
