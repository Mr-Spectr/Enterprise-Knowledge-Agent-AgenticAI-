"""
agentic_workflow.py

Multi-agent orchestrator for the Moodle AI Assistant.
Updated for CSV-only data retrieval.

Agents:
  1. Role Guard   — detect user role from CSV/ID pattern
  2. Context      — load role-scoped dashboard context
  3. Intent       — classify query and enrich from CSV
  4. Data Router  — select the retrieval agent for the intent
  5. Data Agent   — retrieve academic data from students_500.csv
  6. Executor     — structured answer for known intents (no LLM)
  7. Composer     — LLM fallback for complex/unknown intents
"""

import json
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List

from data_agents import route_data_agent
from data_retriever import get_user_context
from agent_reasoner import think as llm_think
from intent_agent import run_intent_agent
from mcp_csv_server import call_tool
from query_planner import plan_query
from rbac import detect_role
from supervisor_agent import (
    create_plan,
    verify_academic_evidence,
    verify_general_response,
    verify_knowledge_evidence,
)


ClassifierFn = Callable[[str], Awaitable[Dict[str, str]]]
ChatFn = Callable[[str, str, str], Awaitable[str]]


class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def _json_dumps(obj, **kwargs):
    return json.dumps(obj, cls=_DecimalEncoder, **kwargs)


@dataclass
class AgentStep:
    agent: str
    action: str
    status: str
    detail: str


@dataclass
class AgentResult:
    answer: str
    role: str
    classification: Dict[str, str]
    user_context: Dict[str, Any]
    trace: List[Dict[str, str]]
    records: List[Dict[str, Any]] = field(default_factory=list)


def _step(agent: str, action: str, status: str, detail: str) -> Dict[str, str]:
    return asdict(AgentStep(agent=agent, action=action, status=status, detail=detail))


def _compact_payload(retrieved: Dict[str, Any]) -> Dict[str, Any]:
    records = retrieved.get("records", [])
    return {
        "intent": retrieved.get("intent"),
        "entity": retrieved.get("entity"),
        "summary": retrieved.get("summary", {}),
        "record_count": len(records),
        "sample_records": records[:12],
        "requester_context": retrieved.get("requester_context", {}),
    }


def _safe(val):
    """Convert Decimal or None to a display-safe value."""
    if isinstance(val, Decimal):
        return float(val)
    return val if val is not None else "N/A"


def _structured_answer(query: str, role: str, payload: Dict[str, Any]) -> str:
    """
    Generate a direct answer from structured data for known intents.
    No LLM call needed — fast and deterministic.
    """
    intent = payload.get("intent", "general")
    summary = payload.get("summary", {})
    entity = payload.get("entity", "general")

    if intent == "student_count":
        return f"There are {summary.get('count', 0)} students in {summary.get('course', entity)}."

    if intent == "course_enrollment":
        # Student asking about their own courses
        if "enrolled_courses" in summary:
            courses = summary.get("enrolled_courses", [])
            names = ", ".join(c.get("fullname", "") for c in courses[:8])
            suffix = f"... and {len(courses) - 8} more" if len(courses) > 8 else ""
            return (
                f"{summary.get('student_name', 'You')} — enrolled in "
                f"{summary.get('count', 0)} courses: {names}{suffix}"
            )
        # Faculty/admin asking about a course's students
        students = summary.get("students", [])
        names = ", ".join(
            s.get("name", "") for s in students[:8] if s.get("name")
        )
        suffix = "..." if summary.get("count", 0) > 8 else ""
        return (
            f"{summary.get('count', 0)} students are enrolled in "
            f"{summary.get('course', entity)}. "
            f"Sample list: {names}{suffix}"
        )

    if intent == "faculty_list":
        faculty = ", ".join(summary.get("faculty", [])[:10])
        return (
            f"Faculty for {summary.get('course', entity)}: "
            f"{faculty or 'No faculty data found.'}"
        )

    if intent == "grades_average":
        if "average_grade" in summary:
            return (
                f"The average grade for {summary.get('course', entity)} is "
                f"{_safe(summary.get('average_grade', 0))} "
                f"(based on {summary.get('grade_count', 0)} graded students)."
            )
        averages = summary.get("course_averages", [])
        parts = [
            f"{item.get('course')}: avg {_safe(item.get('avg_grade', 0))}"
            for item in averages[:6]
        ]
        return "Course-wise grade averages:\n" + "\n".join(parts) if parts else "No grade data available."

    if intent == "attendance_report":
        # Individual student attendance
        if "student_name" in summary:
            return (
                f"Attendance for {summary.get('student_name')} in "
                f"{summary.get('course', 'all courses')}: "
                f"{_safe(summary.get('attendance_percent', 0))}% "
                f"({_safe(summary.get('present', 0))} present, "
                f"{_safe(summary.get('absent', 0))} absent, "
                f"{_safe(summary.get('late', 0))} late, "
                f"{_safe(summary.get('excused', 0))} excused "
                f"out of {summary.get('total_sessions', 0)} sessions)."
            )
        # Class-wide attendance
        return (
            f"Average attendance for {summary.get('course', entity)} is "
            f"{_safe(summary.get('average_attendance_percent', 0))}% "
            f"across {summary.get('student_count', 0)} students."
        )

    if intent == "student_profile":
        if summary.get("faculty_id") is not None:
            courses = ", ".join(summary.get("courses", [])[:5])
            return (
                f"{summary.get('name')} ({summary.get('faculty_id')}) — {summary.get('department', 'N/A')} faculty.\n"
                f"Students: {summary.get('student_count', 0)}; mentees: {summary.get('mentee_count', 0)}.\n"
                f"Average CGPA: {_safe(summary.get('avg_cgpa'))}; average attendance: {_safe(summary.get('avg_attendance'))}%.\n"
                f"Students with backlogs: {summary.get('backlog_students', 0)}.\n"
                f"Courses: {courses or 'No course data found.'}\n"
                f"Contact: {summary.get('email', 'N/A')}, {summary.get('phone', 'N/A')}"
            )

        mentor = summary.get("mentor", {})
        courses = summary.get("enrolled_courses") or summary.get("courses") or []
        course_names = ", ".join(c.get("fullname", "") for c in courses[:5])
        return (
            f"{summary.get('name')} ({summary.get('student_id')}) — "
            f"Semester {summary.get('semester', 'N/A')}, {summary.get('department', 'N/A')}.\n"
            f"CGPA: {_safe(summary.get('cgpa'))}; attendance: {_safe(summary.get('attendance_percent'))}%.\n"
            f"Backlogs: {_safe(summary.get('backlog_count', 0))}"
            f"{f' ({', '.join(summary.get('backlog_courses', []))})' if summary.get('backlog_courses') else ''}\n"
            f"Courses: {course_names or 'No course data found.'}\n"
            f"Mentor: {mentor.get('name', 'Not assigned')}\n"
            f"Contact: {summary.get('email', 'N/A')}, {summary.get('phone', 'N/A')}"
        )

    if intent == "mentor_lookup":
        mentor = summary.get("mentor", {})
        return (
            f"The mentor for {summary.get('name')} is {mentor.get('name', 'Not assigned')}. "
            f"Email: {mentor.get('email', 'N/A')}, phone: {mentor.get('phone', 'N/A')}."
        )

    if intent == "class_teacher_info":
        mentor = summary.get("mentor", {})
        return (
            f"Class teacher for {summary.get('name')}: {mentor.get('name', 'Not assigned')}. "
            f"Email: {mentor.get('email', 'N/A')}, phone: {mentor.get('phone', 'N/A')}."
        )

    if intent == "backlog_report":
        students = summary.get("students", [])
        if not students:
            return "No students with backlogs were found in the current scope."
        rows = [
            f"{s.get('name')} (ID {s.get('student_id')}): "
            f"{s.get('backlog_count')} backlog(s) in {', '.join(s.get('backlog_courses', []))}"
            for s in students[:10]
        ]
        return (
            f"{summary.get('count_with_backlogs', 0)} students currently have backlogs.\n"
            + "\n".join(rows)
        )

    if intent == "contact_lookup":
        contact = summary.get("student_contact", {})
        return (
            f"Contact details for {summary.get('name')}: "
            f"email {contact.get('email', 'N/A')}, "
            f"phone {contact.get('phone', 'N/A')}."
        )

    return f"I found academic data for your query: {query}"


async def run_agentic_workflow(
    *,
    user_id: str,
    query: str,
    data_path: str = "",
    assignments_path: str = "",
    classify_query: ClassifierFn,
    ask_groq: ChatFn,
) -> AgentResult:
    trace: List[Dict[str, str]] = []

    async def reason(agent: str, objective: str, facts: Dict[str, Any]) -> None:
        """Record each agent's constrained LLM deliberation before its action."""
        detail = await llm_think(agent, objective, facts, ask_groq)
        trace.append(_step(agent, "llm_reasoning", "completed", detail))

    # ── Role Guard Agent ──────────────────────────────────────────────────
    await reason("role-guard-agent", "prepare to resolve caller identity", {"user_id": user_id})
    try:
        role = detect_role(user_id)
    except Exception:
        role = "unknown"
    trace.append(_step(
        "role-guard-agent", "detect_role", "completed",
        f"Resolved user role as '{role}'.",
    ))

    # ── Context Agent ─────────────────────────────────────────────────────
    await reason("context-agent", "identify the minimum role-scoped context needed", {"role": role, "user_id": user_id})
    user_context = get_user_context(
        user_id=user_id,
        role=role,
        assignments_path=assignments_path,
    )
    trace.append(_step(
        "context-agent", "load_user_context", "completed",
        "Loaded role-scoped dashboard context.",
    ))

    # ── AI Query Planner Agent ────────────────────────────────────────────
    await reason("query-planner-agent", "choose a safe information route", {"role": role, "query": query})
    plan = await plan_query(query, role, ask_groq)
    route = plan["route"]
    trace.append(_step(
        "query-planner-agent", "plan_query_route", "completed",
        f"Selected {route} route using {plan['source']}: {plan['reason']}",
    ))

    # ── Intent Agent: internal capability resolution, not user-facing routing ─
    await reason("intent-agent", "map the request to an approved academic capability", {"query": query, "user_id": user_id})
    classification, intent_detail = await run_intent_agent(query, classify_query, user_id=user_id)
    trace.append(_step(
        "intent-agent", "classify_and_enrich_intent", "completed", intent_detail,
    ))

    query_type = classification.get("query_type", "general_query")
    intent = classification.get("intent", "general")
    entity = classification.get("entity", "general")

    await reason("supervisor-agent", "review the bounded specialist-agent plan", {"route": route, "intent": intent, "role": role})
    supervisor_plan = create_plan(route, intent, role)
    trace.append(_step(
        "supervisor-agent", "create_bounded_execution_plan", "completed",
        "Planned: " + " -> ".join(task.agent for task in supervisor_plan.tasks),
    ))

    # ── General query → Knowledge Agent (direct LLM) ──────────────────────
    if route == "general":
        await reason("knowledge-agent", "prepare a safe and useful general response", {"query": query, "role": role})
        trace.append(_step(
            "knowledge-agent", "answer_general_query", "in_progress",
            "Sending conceptual query to Groq LLM.",
        ))
        answer = await ask_groq(
            "You are an educational assistant for NMIT. Answer clearly and accurately.",
            f"User role: {role}\nQuestion: {query}",
            "llama-3.3-70b-versatile",
        )
        trace[-1]["status"] = "completed"
        trace[-1]["detail"] = "Returned direct LLM answer for general knowledge query."
        await reason("response-verifier-agent", "check whether the generated response is non-empty and appropriate", {"answer_present": bool(answer)})
        verification = verify_general_response(answer)
        trace.append(_step("response-verifier-agent", "verify_general_response", "completed" if verification.accepted else "failed", verification.reason))
        if not verification.accepted:
            answer = "I could not produce a reliable answer. Please try again."
        return AgentResult(
            answer=answer, role=role, classification=classification,
            user_context=user_context, trace=trace,
        )

    # ── Knowledge query → MCP RAG retrieval + evidence-grounded composer ──
    if route == "knowledge":
        await reason("knowledge-retrieval-agent", "retrieve only approved knowledge-base passages", {"query": query, "role": role})
        evidence = call_tool("search_project_knowledge", {"query": query, "limit": 5}, requester_user_id=user_id)
        await reason("evidence-verifier-agent", "verify that retrieved passages contain approved evidence", {"result_count": evidence.get("result_count", 0)})
        verification = verify_knowledge_evidence(evidence)
        trace.append(_step("knowledge-retrieval-agent", "retrieve_approved_passages", "completed" if verification.accepted else "failed", verification.reason))
        if not verification.accepted:
            trace.append(_step("recovery-agent", "return_transparent_limitation", "completed", "No approved RAG evidence was available."))
            return AgentResult(answer="I could not find an approved knowledge source for that request.", role=role, classification=classification, user_context=user_context, trace=trace)
        await reason("composer-agent", "compose an answer grounded only in verified passages", {"query": query, "evidence_count": evidence.get("result_count", 0)})
        answer = await ask_groq(
            "Answer only from the supplied approved knowledge passages. State when the passages do not answer the question.",
            f"Question: {query}\nEvidence: {_json_dumps(evidence)}",
            "composer",
        )
        trace.append(_step("composer-agent", "compose_grounded_answer", "completed", "Composed answer from verified RAG evidence."))
        return AgentResult(answer=answer, role=role, classification=classification, user_context=user_context, trace=trace)

    # ── Data Router Agent ─────────────────────────────────────────────────
    await reason("data-router-agent", "select the approved specialist retrieval agent", {"intent": intent, "entity": entity, "role": role})
    trace.append(_step(
        "data-router-agent", "select_retrieval_agent", "completed",
        f"Selected retrieval path for intent={intent}, entity={entity}.",
    ))

    # ── Intent-Specific Data Agent ────────────────────────────────────────
    await reason("data-agent", "retrieve only the minimum approved academic data", {"intent": intent, "entity": entity, "role": role})
    data_result = route_data_agent(
        intent=intent,
        entity=entity,
        role=role,
        user_id=user_id,
        assignments_path=assignments_path,
    )
    retrieved = data_result.retrieved
    trace.append(_step(
        data_result.agent,
        data_result.action,
        "completed",
        data_result.detail,
    ))

    await reason("evidence-verifier-agent", "validate record scope and structured evidence", {"record_count": len(retrieved.get("records", [])), "role": role})
    verification = verify_academic_evidence(retrieved, user_id, role)
    trace.append(_step("evidence-verifier-agent", "verify_academic_evidence", "completed" if verification.accepted else "failed", verification.reason))
    if not verification.accepted:
        trace.append(_step("recovery-agent", "return_transparent_limitation", "completed", "Rejected unverified academic result."))
        return AgentResult(answer="I could not verify a reliable, permitted academic record for this request.", role=role, classification=classification, user_context=user_context, trace=trace)

    compact_payload = _compact_payload(retrieved)

    # ── Executor Agent (known intents → no LLM) ──────────────────────────
    if intent in {
        "student_count", "course_enrollment", "faculty_list",
        "grades_average", "attendance_report", "student_profile",
        "mentor_lookup", "class_teacher_info", "backlog_report",
        "contact_lookup",
    }:
        await reason("executor-agent", "prepare a deterministic source-grounded answer", {"intent": intent, "record_count": len(retrieved.get("records", []))})
        trace.append(_step(
            "executor-agent", "compose_structured_answer", "completed",
            "Generated direct tool-based response (no LLM call).",
        ))
        answer = _structured_answer(query, role, compact_payload)

    # ── Composer Agent (complex/unknown → LLM fallback) ───────────────────
    else:
        await reason("composer-agent", "compose from verified structured data without adding facts", {"intent": intent, "record_count": len(retrieved.get("records", []))})
        trace.append(_step(
            "composer-agent", "compose_natural_language_response", "in_progress",
            "Sending database results to Groq LLM for natural language composition.",
        ))
        answer = await ask_groq(
            (
                "You are Moodle AI Assistant for NMIT. "
                "Use the provided structured data from students_500.csv to answer clearly. "
                "Prefer the structured summary. Keep it concise and role-aware."
            ),
            (
                f"User role: {role}\n"
                f"Original query: {query}\n"
                f"Classification: {_json_dumps(classification)}\n"
                f"Database results: {_json_dumps(compact_payload)}\n"
                "Write the final answer."
            ),
            "llama-3.3-70b-versatile",
        )
        trace[-1]["status"] = "completed"
        trace[-1]["detail"] = "Natural-language answer composed from database results."

    return AgentResult(
        answer=answer, role=role, classification=classification,
        user_context=user_context, trace=trace, records=retrieved.get("records", []),
    )
