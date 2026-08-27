"""LLM-first routing with a safe, deterministic fallback."""
from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

ChatFn = Callable[[str, str, str], Awaitable[str]]
SYSTEM_PROMPT = """You are the query-planning agent for an academic assistant.
Classify the request into exactly one route: general, academic_data, or knowledge.
- general: concepts, explanations, writing, or non-institutional help.
- academic_data: a request about records such as grades, attendance, courses, mentors, students, or faculty.
- knowledge: a request about an approved policy, handbook, notice, syllabus, or document.
Return only JSON: {\"route\": \"general|academic_data|knowledge\", \"reason\": \"short reason\"}.
Never invent a database query or an authorization decision."""


async def plan_query(query: str, role: str, ask_ai: ChatFn) -> dict[str, str]:
    fallback = _fallback(query)
    try:
        raw = await ask_ai(SYSTEM_PROMPT, f"Role: {role}\nRequest: {query}", "planner")
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        planned = json.loads(match.group(0) if match else raw)
        route = planned.get("route")
        if route in {"general", "academic_data", "knowledge"}:
            return {"route": route, "reason": str(planned.get("reason", "AI planner")), "source": "groq"}
    except Exception:
        pass
    return {"route": fallback, "reason": "Deterministic fallback", "source": "fallback"}


def _fallback(query: str) -> str:
    text = query.lower()
    if any(word in text for word in ("policy", "handbook", "notice", "syllabus", "document", "rag", "mcp")):
        return "knowledge"
    if any(word in text for word in ("cgpa", "grade", "attendance", "mentor", "course", "student", "faculty", "backlog", "semester", "contact")):
        return "academic_data"
    return "general"
