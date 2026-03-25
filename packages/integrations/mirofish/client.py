"""
mirofish/client.py — MiroFish swarm simulation client.

Context: MiroFish is a multi-agent simulation engine that predicts how
events will unfold. We submit a seed (current events) and a forecast
demand (what we want to predict), and it returns predicted trends.

MiroFish runs as a separate local server on port 5001.
This client handles its absence gracefully — returns None/empty when down.

GitHub: https://github.com/666ghj/MiroFish
Start:  cd MiroFish && python backend/main.py

Imports: httpx, packages.core
Imported by: packages/integrations/mirofish/seeds.py, packages/agents/
"""

from __future__ import annotations
import httpx
from packages.core.errors import IntegrationError
from packages.core.logger import get_logger

log = get_logger(__name__)


class MiroFishClient:
    """Client for MiroFish swarm simulation API.

    All methods return None/empty when MiroFish is unavailable —
    the pipeline continues without trend simulation.
    """

    def __init__(self, base_url: str = "http://localhost:5001") -> None:
        self.base_url = base_url
        self._http = httpx.AsyncClient(base_url=base_url, timeout=300.0)

    async def submit_seed(
        self,
        seed_text: str,
        forecast_demand: str,
        max_rounds: int = 30,
    ) -> str | None:
        """Submit a seed event for simulation.

        Args:
            seed_text: Current events to simulate from
            forecast_demand: What to predict (e.g. YouTube trends in Pakistan)
            max_rounds: Simulation rounds (keep under 40 for free Zep tier)

        Returns:
            simulation_id string, or None if MiroFish unavailable
        """
        try:
            resp = await self._http.post(
                "/api/simulation",
                json={
                    "seed": seed_text,
                    "forecast": forecast_demand,
                    "max_rounds": max_rounds,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            sim_id = data.get("simulation_id") or data.get("id")
            log.info("mirofish_submitted", simulation_id=sim_id)
            return sim_id
        except httpx.ConnectError:
            log.warning("mirofish_unavailable: Start with: cd MiroFish && python backend/main.py")
            return None
        except Exception as e:
            log.warning("mirofish_error", method="submit_seed", error=str(e))
            return None

    async def get_status(self, simulation_id: str) -> dict:
        """Check simulation progress.

        Returns:
            {"status": "running"|"complete", "progress": 0.0-1.0}
            or {"status": "unknown"} if unavailable
        """
        try:
            resp = await self._http.get(f"/api/simulation/{simulation_id}/status")
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            return {"status": "unknown"}
        except Exception as e:
            log.warning("mirofish_error", method="get_status", error=str(e))
            return {"status": "unknown"}

    async def get_report(self, simulation_id: str) -> dict:
        """Get prediction report after simulation completes.

        Returns:
            Dict with predicted_trends, key_events, recommended_angles, confidence
            or {} if unavailable
        """
        try:
            resp = await self._http.get(f"/api/simulation/{simulation_id}/report")
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            return {}
        except Exception as e:
            log.warning("mirofish_error", method="get_report", error=str(e))
            return {}

    async def interact(self, simulation_id: str, question: str) -> str:
        """Ask a question about the simulated world post-completion.

        Returns:
            Answer string, or "" if unavailable
        """
        try:
            resp = await self._http.post(
                f"/api/simulation/{simulation_id}/interact",
                json={"question": question},
            )
            resp.raise_for_status()
            return resp.json().get("answer", "")
        except httpx.ConnectError:
            return ""
        except Exception as e:
            log.warning("mirofish_error", method="interact", error=str(e))
            return ""

    async def close(self) -> None:
        await self._http.aclose()
