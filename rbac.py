"""
rbac.py

CSV-only identity and permissions.
Student USNs are resolved from students_500.csv; ADM*/FAC* ids are accepted
for admin/faculty UI actions without any external database.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from csv_db import find_student


_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"view_own_data", "view_student_data", "view_course_data", "assign_mentor", "general_query"},
    "faculty": {"view_course_data", "view_own_data", "assign_mentor", "general_query"},
    "student": {"view_own_data", "general_query"},
    "unknown": {"general_query"},
}

_SELF_INTENTS = {
    "student_profile", "mentor_lookup", "class_teacher_info", "contact_lookup",
    "grades_average", "attendance_report", "backlog_report", "course_enrollment",
    "student_count", "faculty_list",
}


@dataclass
class RoleIdentity:
    role: str
    user_id: str
    moodle_id: int
    username: str
    fullname: str
    email: str
    permissions: set[str] = field(default_factory=set)

    def can(self, action: str) -> bool:
        return action in self.permissions


def resolve_identity(user_id: str) -> RoleIdentity:
    raw = (user_id or "").strip()
    upper = raw.upper()

    if upper.startswith("ADM"):
        role = "admin"
        return RoleIdentity(role, raw, 0, raw, "Administrator", "", set(_PERMISSIONS[role]))
    if upper.startswith("FAC"):
        role = "faculty"
        return RoleIdentity(role, raw, 0, raw, "Faculty", "", set(_PERMISSIONS[role]))

    student = find_student(raw)
    if student:
        role = "student"
        return RoleIdentity(
            role=role,
            user_id=student["usn"],
            moodle_id=student["id"],
            username=student["usn"],
            fullname=student["name"],
            email=student["email"],
            permissions=set(_PERMISSIONS[role]),
        )

    role = "unknown"
    return RoleIdentity(role, raw, 0, raw, "", "", set(_PERMISSIONS[role]))


def detect_role(user_id: str) -> str:
    return resolve_identity(user_id).role


def action_for_intent_and_role(intent: str, role: str) -> str:
    if intent == "general":
        return "general_query"
    if role == "student" and intent in _SELF_INTENTS:
        return "view_own_data"
    if role in {"faculty", "admin"}:
        return "view_course_data"
    return "general_query"


def check_permission(identity: RoleIdentity, action: str) -> None:
    if not identity.can(action):
        raise PermissionError(f"[{identity.role.upper()}] Access denied.")
