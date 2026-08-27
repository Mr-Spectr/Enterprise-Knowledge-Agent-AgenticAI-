"""Constrained LLM reasoning used by every workflow agent.

The output is advisory trace context only. Permission checks, tool selection,
data retrieval, and evidence acceptance remain deterministic in code.
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

ChatFn = Callable[[str, str, str], Awaitable[str]]

SYSTEM = """You are a specialist agent in a controlled academic workflow.
Think briefly before acting. Return exactly one JSON object with keys:
{"focus":"what to check", "next_action":"short action", "risk":"short risk or none"}.
You cannot authorize access, write SQL, reveal hidden data, or change the tool plan.
Your JSON is advisory; deterministic policy code makes the final decision."""


async def think(
    agent: str,
    objective: str,
    facts: dict[str, Any],
    ask_ai: ChatFn,
) -> str:
    """Return compact LLM reasoning, with a safe deterministic fallback."""
    try:
        response = await ask_ai(
            SYSTEM,
            json.dumps({"agent": agent, "objective": objective, "facts": facts}, default=str),
            "agent-reasoner",
        )
        compact = " ".join(str(response).split())
        return compact[:500] if compact else "LLM returned no advisory reasoning."
    except Exception:
        return "LLM reasoning unavailable; continuing with deterministic safeguards."
