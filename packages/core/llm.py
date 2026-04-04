"""
llm.py — Centralised LLM factory for FreeRouter-backed CrewAI agents.

All CrewAI agents that need an LLM routed through FreeRouter should use
``freerouter_llm()`` from this module.

Usage::

    from packages.core.llm import freerouter_llm

    agent = Agent(
        role="Researcher",
        llm=freerouter_llm(model="gpt-4o-mini"),
        ...
    )

CrewAI internally uses LiteLLM which reads OPENAI_API_BASE and OPENAI_API_KEY
environment variables. By setting these to point at FreeRouter, all LLM calls
are routed through the proxy without needing to pass ChatOpenAI objects.
"""

from __future__ import annotations

import os

from .config import get_settings


def _ensure_freerouter_env() -> None:
    """Set OPENAI_API_BASE and OPENAI_API_KEY for CrewAI/LiteLLM integration.

    CrewAI's internal LLM layer uses LiteLLM, which reads these environment
    variables. By pointing them at FreeRouter, all CrewAI agent LLM calls
    go through the proxy automatically.
    """
    settings = get_settings()
    api_base = f"{settings.FREEROUTER_URL}/v1"
    api_key = settings.FREEROUTER_API_KEY

    # Only set if not already overridden by the user
    if not os.environ.get("OPENAI_API_BASE"):
        os.environ["OPENAI_API_BASE"] = api_base
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = api_key


def freerouter_llm(
    model: str = "default",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Return a model identifier string for CrewAI agents.

    CrewAI (>= 0.86) accepts a string model name and handles LLM
    instantiation internally via LiteLLM. This function ensures
    FreeRouter environment variables are set and returns the model string.

    Parameters
    ----------
    model:
        Model identifier recognised by FreeRouter (e.g. ``"gpt-4o-mini"``,
        ``"auto"``).  Falls back to
        ``"default"`` which lets FreeRouter pick an available provider.
    temperature:
        Sampling temperature (0.0 – 2.0). Stored but not directly used —
        CrewAI handles this internally.
    max_tokens:
        Maximum tokens in the completion response. Stored but not directly
        used — CrewAI handles this internally.

    Note:
        Temperature and max_tokens are accepted for API compatibility but
        are not applied here. Configure them on the Agent if needed.
    """
    _ensure_freerouter_env()
    return model
