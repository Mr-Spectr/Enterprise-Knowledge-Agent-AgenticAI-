from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "view_own_data",
        "view_student_data",
        "view_course_data",
        "assign_mentor",
        "general_query",
    },
    "faculty": {
        "view_course_data",
        "assign_mentor",
        "general_query",
    },
    "student": {
        "view_own_data",
        "general_query",
    },
    "unknown": {
        "general_query",
    },
}

_DENIED: dict[str, str] = {
    "view_own_data":       "Access denied.",
    "view_student_data":   "You do not have permission to view student records.",
    "view_course_data":    "You do not have permission to view course data.",
    "assign_mentor":       "Only faculty and administrators can assign mentors.",
    "general_query":       "Access denied.",
}


@dataclass
class RoleIdentity:
    role: str
    user_id: str
    canonical: str
    permissions: set[str] = field(default_factory=set)

    def can(self, action: str) -> bool:
        return action in self.permissions

_SELF_INTENTS = {
    "student_profile", "mentor_lookup", "class_teacher_info",
    "contact_lookup", "grades_average", "attendance_report", "backlog_report",
    "faculty_profile"   
}

_INTENT_ACTION = {
    "student_count":     "view_course_data",
    "course_enrollment": "view_course_data",
    "faculty_list":      "view_course_data",
    "grades_average":    "view_own_data",
    "attendance_report": "view_own_data",
    "backlog_report":    "view_own_data",
    "student_profile":   "view_own_data",
    "mentor_lookup":     "view_own_data",
    "class_teacher_info":"view_own_data",
    "contact_lookup":    "view_own_data",
    "faculty_profile":   "view_course_data",   
    "general":           "general_query",
}


def action_for_intent_and_role(intent: str, role: str) -> str:
    if intent == "general":
        return "general_query"

    if role == "student":
        if intent in _SELF_INTENTS:
            return "view_own_data"
        return "view_course_data"

    if role == "faculty":
        return "view_course_data"

    if role == "admin":
        return "view_course_data"

    return "view_course_data"

def resolve_identity(user_id: str) -> RoleIdentity:
    if not user_id or not user_id.strip():
        return RoleIdentity("unknown", "", "", set(_PERMISSIONS["unknown"]))

    v = user_id.strip().upper()

    if v.startswith("ADM"):
        role, canonical = "admin", v
    elif v.startswith("FAC"):
        role, canonical = "faculty", v
    elif v.startswith("STU"):
        role = "student"
        canonical = re.sub(r"^STU[-_:]?", "", v) or v
    elif re.match(r"^\d[A-Z0-9]{6,}$", v):
        role, canonical = "student", v
    else:
        role, canonical = "unknown", v

    return RoleIdentity(
        role=role,
        user_id=user_id,
        canonical=canonical,
        permissions=set(_PERMISSIONS.get(role, _PERMISSIONS["unknown"]))
    )


def check_permission(identity: RoleIdentity, action: str) -> None:
    if not identity.can(action):
        msg = _DENIED.get(action, "Access denied.")
        raise PermissionError(f"[{identity.role.upper()}] {msg}")

def faculty_scope(identity: RoleIdentity, df: Any) -> Any:
    if identity.role == "admin":
        return df
    if identity.role != "faculty":
        return df.iloc[0:0]

    canonical = identity.canonical.upper()

    if "faculty_id" in df.columns:
        return df[df["faculty_id"].str.upper() == canonical]

    if "class_teacher_id" in df.columns:
        return df[df["class_teacher_id"].str.upper() == canonical]

    return df.iloc[0:0]


def student_scope(identity: RoleIdentity, df: Any) -> Any:
    if identity.role == "admin":
        return df
    return df[df["student_id"].str.upper() == identity.canonical.upper()]

def handle_faculty_query(intent: str, identity: RoleIdentity, df: Any) -> str:

    if intent == "faculty_profile":
        return f"""Faculty Profile

Faculty ID: {identity.canonical}
Role: Faculty

Access:
- Your courses
- Your students
- Attendance & grades
- Mentor assignment
"""

    scoped = faculty_scope(identity, df)

    if scoped.empty:
        return "No data found for your faculty ID."

    if intent == "student_count":
        return f"Total students under you: {len(scoped)}"

    if intent == "course_enrollment":
        if "course" in scoped.columns:
            courses = scoped["course"].dropna().unique()
            return "Courses you handle: " + ", ".join(map(str, courses))
        return "Course data not available."

    if intent == "attendance_report":
        if "attendance" in scoped.columns:
            avg = scoped["attendance"].mean()
            return f"Average attendance: {avg:.2f}%"
        return "Attendance data not available."

    if intent == "grades_average":
        if "marks" in scoped.columns:
            avg = scoped["marks"].mean()
            return f"Average marks: {avg:.2f}"
        return "Marks data not available."

    if intent == "backlog_report":
        if "backlogs" in scoped.columns:
            total = scoped["backlogs"].sum()
            return f"Total backlogs in your class: {int(total)}"
        return "Backlog data not available."

    return "Faculty request processed."

def process_query(user_id: str, intent: str, df: Any):
    identity = resolve_identity(user_id)
    action = action_for_intent_and_role(intent, identity.role)

    check_permission(identity, action)

    # ✅ FACULTY FLOW
    if identity.role == "faculty":
        return handle_faculty_query(intent, identity, df)

    # Existing logic (student/admin stays same)
    return "Processed using existing student/admin flow"