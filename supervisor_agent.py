"""Closed-loop supervisor for the academic multi-agent workflow.

The supervisor plans only from an allow-list of agents.  It cannot issue SQL,
override RBAC, or select an unregistered tool.  A verifier must accept the
evidence before a result is returned to the user.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentTask:
    agent: str
    objective: str


@dataclass(frozen=True)
class SupervisorPlan:
    route: str
    tasks: tuple[AgentTask, ...]
    recovery_task: AgentTask


@dataclass(frozen=True)
class Verification:
    accepted: bool
    reason: str


def create_plan(route: str, intent: str, role: str) -> SupervisorPlan:
    """Create a bounded plan from safe, registered agent capabilities."""
    base = [AgentTask("role-guard-agent", "enforce caller identity and permissions")]
    if route == "academic_data":
        base += [
            AgentTask("data-agent", f"retrieve approved academic data for {intent}"),
            AgentTask("evidence-verifier-agent", "check scope, source, and missing values"),
            AgentTask("executor-agent", "compose a source-grounded response"),
        ]
    elif route == "knowledge":
        base += [
            AgentTask("knowledge-retrieval-agent", "retrieve visible RAG passages with citations"),
            AgentTask("evidence-verifier-agent", "require at least one approved source"),
            AgentTask("composer-agent", "answer only from retrieved passages"),
        ]
    else:
        base += [
            AgentTask("knowledge-agent", "answer the general request"),
            AgentTask("response-verifier-agent", "check response usefulness and safety"),
        ]
    return SupervisorPlan(
        route=route,
        tasks=tuple(base),
        recovery_task=AgentTask("recovery-agent", "return a transparent limitation instead of unsupported data"),
    )


def verify_academic_evidence(payload: dict[str, Any], requester_id: str, role: str) -> Verification:
    """Ensure academic answers are based on a controlled tool result."""
    if not isinstance(payload, dict) or not isinstance(payload.get("summary"), dict):
        return Verification(False, "The data tool did not return a structured summary.")
    records = payload.get("records", [])
    if role == "student" and records:
        ids = {str(record.get("usn") or record.get("student_id") or "").upper() for record in records}
        if ids and requester_id.upper() not in ids:
            return Verification(False, "The requested record is outside the student's permitted scope.")
    return Verification(True, "Structured evidence passed role and shape checks.")


def verify_knowledge_evidence(result: dict[str, Any]) -> Verification:
    sources = result.get("results", []) if isinstance(result, dict) else []
    return Verification(bool(sources), "Retrieved approved knowledge sources." if sources else "No approved knowledge source was found.")


def verify_general_response(answer: str) -> Verification:
    return Verification(bool(answer and answer.strip()), "General response is non-empty." if answer else "The language model returned no response.")
