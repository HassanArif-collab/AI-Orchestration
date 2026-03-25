"""
mirofish/seeds.py — Helper functions to create well-formatted MiroFish seeds.

Context: MiroFish needs structured seed text describing current world events,
and a forecast demand describing what we want to predict. These helpers
format data into the patterns MiroFish understands best.

Pure functions — no external calls, fully testable without MiroFish running.

Imports: datetime only
Imported by: packages/agents/ (trend looker agent)
"""

from __future__ import annotations
from datetime import date


def create_geopolitical_seed(
    events: list[str],
    region: str = "South Asia",
) -> str:
    """Format geopolitical events into a MiroFish seed text."""
    today = date.today().strftime("%B %d, %Y")
    event_lines = "\n".join(f"- {e}" for e in events)
    return (
        f"[{today}] Geopolitical situation in {region}:\n"
        f"{event_lines}\n\n"
        f"Region context: Pakistan, India, Afghanistan and neighbouring states. "
        f"Major factors include economic pressures, political transitions, "
        f"and technology policy shifts."
    )


def create_tech_trend_seed(
    developments: list[str],
    focus: str = "AI",
) -> str:
    """Format technology developments into a MiroFish seed."""
    today = date.today().strftime("%B %d, %Y")
    dev_lines = "\n".join(f"- {d}" for d in developments)
    return (
        f"[{today}] Technology landscape — {focus}:\n"
        f"{dev_lines}\n\n"
        f"Context: Emerging markets including Pakistan are experiencing "
        f"rapid {focus} adoption with limited regulatory frameworks."
    )


def create_audience_forecast(
    audience: str = "Pakistani YouTube viewers, ages 18-35",
    timeframe: str = "2-4 weeks",
) -> str:
    """Create a standard forecast demand string for YouTube prediction."""
    return (
        f"Predict how YouTube content consumption will shift among "
        f"{audience} over the next {timeframe}. "
        f"Specifically: which topics will trend, what emotional tones will resonate, "
        f"and what video formats (explainer, documentary, reaction) will gain traction."
    )


def create_combined_seed(
    geopolitical: list[str],
    tech: list[str],
    audience_context: str = "Pakistani YouTube audience",
) -> tuple[str, str]:
    """Create both seed_text and forecast_demand for a combined analysis.

    Returns:
        (seed_text, forecast_demand) tuple ready for MiroFishClient.submit_seed()
    """
    geo_seed = create_geopolitical_seed(geopolitical)
    tech_seed = create_tech_trend_seed(tech)
    seed_text = f"{geo_seed}\n\n{tech_seed}"
    forecast_demand = create_audience_forecast(audience=audience_context)
    return seed_text, forecast_demand
