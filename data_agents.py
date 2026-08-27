"""
data_agents.py

Intent-specific CSV retrieval agents.
The intent-agent decides the intent; this router sends the request to the
dedicated data agent for that intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from mcp_csv_server import call_tool


@dataclass(frozen=True)
class DataAgentResult:
    agent: str
    action: str
    detail: str
    retrieved: Dict[str, Any]


def _run(
    *,
    agent: str,
    action: str,
    detail: str,
    intent: str,
    entity: str,
    role: str,
    user_id: str,
    assignments_path: str,
) -> DataAgentResult:
    return DataAgentResult(
        agent=agent,
        action=action,
        detail=detail,
        retrieved=call_tool(
            "retrieve_data",
            {
                "intent": intent,
                "entity": entity,
                "role": role,
                "user_id": user_id,
                "assignments_path": assignments_path,
            },
            requester_user_id=user_id,
        ),
    )


def _profile_agent(**kwargs) -> DataAgentResult:
    return _run(
        agent="profile-data-agent",
        action="retrieve_student_profile",
        detail="Retrieved student profile, CGPA, courses, mentor, attendance, and backlogs from CSV.",
        **kwargs,
    )


def _grade_agent(**kwargs) -> DataAgentResult:
    return _run(
        agent="grade-data-agent",
        action="retrieve_grades",
        detail="Retrieved CGPA and average grade data from CSV student records.",
        **kwargs,
    )


def _course_agent(**kwargs) -> DataAgentResult:
    return _run(
        agent="course-data-agent",
        action="retrieve_courses",
        detail="Retrieved enrolled courses or course catalog from CSV-derived course data.",
        **kwargs,
    )


def _attendance_agent(**kwargs) -> DataAgentResult:
    return _run(
        agent="attendance-data-agent",
        action="retrieve_attendance",
        detail="Retrieved derived attendance summary from CSV student record.",
        **kwargs,
    )


def _mentor_agent(**kwargs) -> DataAgentResult:
    return _run(
        agent="mentor-data-agent",
        action="retrieve_mentor",
        detail="Retrieved assigned mentor/class teacher from CSV-derived assignment.",
        **kwargs,
    )


def _backlog_agent(**kwargs) -> DataAgentResult:
    return _run(
        agent="backlog-data-agent",
        action="retrieve_backlogs",
        detail="Retrieved derived backlog count and backlog subjects from CSV data.",
        **kwargs,
    )


def _contact_agent(**kwargs) -> DataAgentResult:
    return _run(
        agent="contact-data-agent",
        action="retrieve_contact",
        detail="Retrieved student email and phone from CSV.",
        **kwargs,
    )


def _count_agent(**kwargs) -> DataAgentResult:
    return _run(
        agent="count-data-agent",
        action="retrieve_student_count",
        detail="Counted students from students_500.csv.",
        **kwargs,
    )


def _faculty_agent(**kwargs) -> DataAgentResult:
    return _run(
        agent="faculty-data-agent",
        action="retrieve_faculty",
        detail="Retrieved mentor/faculty directory from CSV-derived assignments.",
        **kwargs,
    )


def _general_agent(**kwargs) -> DataAgentResult:
    return _run(
        agent="csv-data-agent",
        action="retrieve_csv_data",
        detail="Retrieved CSV data using the generic CSV retrieval fallback.",
        **kwargs,
    )


AGENTS: dict[str, Callable[..., DataAgentResult]] = {
    "student_profile": _profile_agent,
    "grades_average": _grade_agent,
    "course_enrollment": _course_agent,
    "attendance_report": _attendance_agent,
    "mentor_lookup": _mentor_agent,
    "class_teacher_info": _mentor_agent,
    "backlog_report": _backlog_agent,
    "contact_lookup": _contact_agent,
    "student_count": _count_agent,
    "faculty_list": _faculty_agent,
}


def route_data_agent(
    *,
    intent: str,
    entity: str,
    role: str,
    user_id: str,
    assignments_path: str,
) -> DataAgentResult:
    agent = AGENTS.get(intent, _general_agent)
    return agent(
        intent=intent,
        entity=entity,
        role=role,
        user_id=user_id,
        assignments_path=assignments_path,
    )
