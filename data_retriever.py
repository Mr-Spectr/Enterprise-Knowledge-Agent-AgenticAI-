"""
data_retriever.py

CSV-only data retrieval layer.
All student data comes from /Users/palakpandit/Desktop/students_500.csv.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from csv_db import (
    all_backlogs,
    all_courses,
    attendance_summary,
    backlog_summary,
    contact_summary,
    default_context,
    faculty_profile,
    find_student,
    load_students,
    mentor_summary,
    profile_summary,
    student_count,
    students_for_faculty,
)


def _clean(obj: Any) -> Any:
    return obj


def get_user_context(
    data_path: str = "",
    user_id: str = "",
    role: str = "student",
    assignments_path: str = "",
) -> Dict[str, Any]:
    return default_context(user_id=user_id, role=role if role != "unknown" else "student")


def _target_student(entity: str, user_id: str) -> Dict[str, Any] | None:
    return find_student(entity) or find_student(user_id)


def _student_count() -> Dict[str, Any]:
    return {
        "count": student_count(),
        "course": "students_500.csv",
        "source": "students_500.csv",
    }


def _course_enrollment(entity: str, user_id: str, role: str) -> Dict[str, Any]:
    student = find_student(user_id)
    if role == "student" and student:
        return {
            "course": student["department"],
            "student_name": student["name"],
            "count": student["course_count"],
            "enrolled_courses": student["enrolled_courses"],
            "source": "students_500.csv",
        }

    if role == "faculty":
        students = students_for_faculty(user_id)
        return {
            "course": "my_students",
            "count": len(students),
            "students": [
                {
                    "student_id": s["usn"],
                    "name": s["name"],
                    "username": s["usn"],
                    "email": s["email"],
                    "semester": s["semester"],
                    "cgpa": s["cgpa"],
                    "attendance_percent": s["attendance_percent"],
                    "backlog_count": s["backlog_count"],
                }
                for s in students[:50]
            ],
            "source": "students_500.csv",
        }

    dept = (entity or "").strip().upper()
    students = [
        {
            "student_id": s["usn"],
            "name": s["name"],
            "username": s["usn"],
            "email": s["email"],
            "semester": s["semester"],
            "cgpa": s["cgpa"],
        }
        for s in load_students()
        if not dept or dept == "GENERAL" or s["department"].upper() == dept
    ]
    return {
        "course": dept if dept and dept != "GENERAL" else "all_students",
        "count": len(students),
        "students": students[:50],
        "source": "students_500.csv",
    }


def _grades_average(entity: str, user_id: str) -> Dict[str, Any]:
    student = _target_student(entity, user_id)
    if student:
        return profile_summary(student)

    students = load_students()
    avg = round(sum(s["cgpa"] for s in students) / len(students), 2) if students else 0
    return {
        "course": "students_500.csv",
        "average_grade": avg,
        "grade_count": len(students),
        "source": "students_500.csv",
    }


def _faculty_average(user_id: str) -> Dict[str, Any]:
    students = students_for_faculty(user_id)
    avg = round(sum(s["cgpa"] for s in students) / len(students), 2) if students else 0
    return {
        "course": "my_students",
        "average_grade": avg,
        "grade_count": len(students),
        "source": "students_500.csv",
    }


def _faculty_attendance(user_id: str) -> Dict[str, Any]:
    students = students_for_faculty(user_id)
    avg = round(sum(s["attendance_percent"] for s in students) / len(students), 2) if students else 0
    return {
        "course": "my_students",
        "average_attendance_percent": avg,
        "student_count": len(students),
        "students": students[:12],
        "source": "students_500.csv",
    }


def _faculty_backlogs(user_id: str) -> Dict[str, Any]:
    students = [
        {
            "student_id": s["usn"],
            "name": s["name"],
            "backlog_count": s["backlog_count"],
            "backlog_courses": s["backlog_courses"],
        }
        for s in students_for_faculty(user_id)
        if s["backlog_count"] > 0
    ]
    return {
        "count_with_backlogs": len(students),
        "students": students[:30],
        "source": "students_500.csv",
    }


def _faculty_list(entity: str) -> Dict[str, Any]:
    mentors = []
    seen = set()
    for student in load_students():
        mentor = student["mentor"]
        if mentor["email"] in seen:
            continue
        seen.add(mentor["email"])
        mentors.append({"name": mentor["name"], "email": mentor["email"], "role_type": "mentor"})
    return {
        "course": entity if entity and entity != "general" else "all_students",
        "faculty": [m["name"] for m in mentors],
        "faculty_details": mentors,
        "count": len(mentors),
        "source": "students_500.csv",
    }


def _course_catalog() -> Dict[str, Any]:
    courses = all_courses()
    return {
        "course": "all_courses",
        "count": len(courses),
        "enrolled_courses": courses,
        "source": "students_500.csv",
    }


def retrieve_data(
    data_path: str = "",
    intent: str = "general",
    entity: str = "general",
    role: str = "student",
    user_id: str = "",
    assignments_path: str = "",
) -> Dict[str, Any]:
    student = _target_student(entity, user_id)
    result: Dict[str, Any] = {
        "intent": intent,
        "entity": student["usn"] if student else (entity if entity != "general" else "general"),
        "records": [student] if student else [],
        "summary": {},
    }

    if intent == "student_count":
        result["summary"] = _student_count()
    elif intent == "course_enrollment":
        result["summary"] = _course_enrollment(entity, user_id, role) if (student or role == "faculty") else _course_catalog()
    elif intent == "faculty_list":
        result["summary"] = _faculty_list(entity)
    elif intent in {"grades_average", "student_profile"}:
        if role == "faculty" and not student and intent == "student_profile":
            result["summary"] = faculty_profile(user_id) or {}
        elif role == "faculty" and not student and intent == "grades_average":
            result["summary"] = _faculty_average(user_id)
        elif not student:
            result["summary"] = _grades_average(entity, user_id)
        else:
            result["summary"] = profile_summary(student)
    elif intent == "attendance_report":
        if role == "faculty" and not student:
            result["summary"] = _faculty_attendance(user_id)
            return _clean(result)
        if not student:
            raise ValueError("No matching student was found for attendance lookup.")
        result["summary"] = attendance_summary(student)
    elif intent == "mentor_lookup":
        if not student:
            raise ValueError("No matching student was found for mentor lookup.")
        result["summary"] = mentor_summary(student)
    elif intent == "class_teacher_info":
        if not student:
            raise ValueError("No matching student was found for class teacher lookup.")
        result["summary"] = mentor_summary(student)
        result["summary"]["note"] = "Using assigned mentor as class teacher in the CSV-only dataset."
    elif intent == "backlog_report":
        if role == "faculty" and not student:
            result["summary"] = _faculty_backlogs(user_id)
        else:
            result["summary"] = backlog_summary(student) if student else all_backlogs()
    elif intent == "contact_lookup":
        if not student:
            raise ValueError("No matching student was found for contact lookup.")
        result["summary"] = contact_summary(student)
    else:
        result["summary"] = {
            "message": "CSV database is connected, but no specialized intent was triggered.",
            "source": "students_500.csv",
        }

    return _clean(result)


def assign_mentor(
    data_path: str = "",
    assignments_path: str = "",
    actor_role: str = "",
    actor_user_id: str = "",
    student_id: str = "",
    mentor_name: str = "",
    mentor_email: str = "",
    mentor_phone: str = "",
) -> Dict[str, Any]:
    """
    CSV-only mode does not mutate students_500.csv. This endpoint validates
    the student and returns the requested mentor assignment for UI feedback.
    """
    student = find_student(student_id)
    if not student:
        raise ValueError(f"Student '{student_id}' was not found in students_500.csv.")

    assignment = {
        "mentor_name": mentor_name.strip(),
        "mentor_email": mentor_email.strip(),
        "mentor_phone": mentor_phone.strip(),
        "assigned_by": actor_user_id.strip(),
    }

    path = Path(assignments_path)
    if assignments_path:
        overrides: dict = {}
        if path.exists():
            try:
                overrides = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                overrides = {}
        overrides[student["usn"]] = assignment
        path.write_text(json.dumps(overrides, indent=2), encoding="utf-8")

    return {
        "message": f"Mentor updated for {student['name']}.",
        "student_id": student["usn"],
        "student_name": student["name"],
        "mentor": assignment,
    }
