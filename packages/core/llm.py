"""
llm.py — Centralised LLM factory for FreeRouter-backed ChatOpenAI instances.

All CrewAI agents and LangChain-based components that need a ChatOpenAI
instance routed through FreeRouter should use ``_freerouter_llm()`` from
this module instead of constructing ChatOpenAI inline.

Usage::

    from packages.core.llm import freerouter_llm

    agent = Agent(
        role="Researcher",
        llm=freerouter_llm(model="gpt-4o-mini"),
        ...
    )
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from .config import get_settings


def freerouter_llm(
    model: str = "default",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> ChatOpenAI:
    """Return a ``ChatOpenAI`` instance pointed at the FreeRouter proxy.

    Parameters
    ----------
    model:
        Model identifier recognised by FreeRouter (e.g. ``"gpt-4o-mini"``,
        ``"openrouter/google/gemini-2.0-flash-001"``).  Falls back to
        ``"default"`` which lets FreeRouter pick an available provider.
    temperature:
        Sampling temperature (0.0 – 2.0).
    max_tokens:
        Maximum tokens in the completion response.
    """
    settings = get_settings()
    return ChatOpenAI(
        model=model,
        openai_api_base=f"{settings.FREEROUTER_URL}/v1",
        openai_api_key=settings.FREEROUTER_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens,
    )
