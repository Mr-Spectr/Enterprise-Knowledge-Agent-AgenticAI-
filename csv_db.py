"""
csv_db.py

CSV-only data adapter for the Moodle AI Assistant.
The app treats students_500.csv as the single source of truth and derives
mentor, attendance, and backlog fields for every student.
"""

from __future__ import annotations

import csv
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from academic_store import fetch_records


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV_PATH = BASE_DIR / "data" / "students.csv"
CSV_PATH = Path(os.getenv("STUDENT_DB_CSV_PATH", DEFAULT_CSV_PATH))
USN_RE = re.compile(r"\b[0-9][a-z]{2}[0-9]{2}[a-z]{2}[0-9]{3}\b", re.IGNORECASE)

MENTORS = [
    {"name": "Dr. Asha Rao", "email": "asha.rao@nmit.ac.in", "phone": "9000001001"},
    {"name": "Prof. Kiran Kumar", "email": "kiran.kumar@nmit.ac.in", "phone": "9000001002"},
    {"name": "Dr. Meera Nair", "email": "meera.nair@nmit.ac.in", "phone": "9000001003"},
    {"name": "Prof. Sanjay Iyer", "email": "sanjay.iyer@nmit.ac.in", "phone": "9000001004"},
    {"name": "Dr. Kavya Shetty", "email": "kavya.shetty@nmit.ac.in", "phone": "9000001005"},
]

COURSE_CATALOG = {
    1: [
        ("MATH101", "Engineering Mathematics I"),
        ("PHY101", "Engineering Physics"),
        ("CSE101", "Programming in C"),
        ("ESC101", "Basic Electrical Engineering"),
        ("HSM101", "Professional Communication"),
    ],
    2: [
        ("MATH102", "Engineering Mathematics II"),
        ("CHE102", "Engineering Chemistry"),
        ("CSE102", "Python Programming"),
        ("ESC102", "Engineering Graphics"),
        ("HSM102", "Environmental Studies"),
    ],
    3: [
        ("ISE201", "Data Structures"),
        ("ISE202", "Discrete Mathematics"),
        ("ISE203", "Digital Logic Design"),
        ("ISE204", "Object Oriented Programming"),
        ("ISE205", "Computer Organization"),
    ],
    4: [
        ("ISE251", "Design and Analysis of Algorithms"),
        ("ISE252", "Database Management Systems"),
        ("ISE253", "Operating Systems"),
        ("ISE254", "Microcontrollers"),
        ("ISE255", "Software Engineering"),
    ],
    5: [
        ("ISE301", "Computer Networks"),
        ("ISE302", "Web Technologies"),
        ("ISE303", "Artificial Intelligence"),
        ("ISE304", "Theory of Computation"),
        ("ISE305", "Data Analytics"),
    ],
    6: [
        ("ISE351", "Machine Learning"),
        ("ISE352", "Cloud Computing"),
        ("ISE353", "Information Security"),
        ("ISE354", "Mobile Application Development"),
        ("ISE355", "Big Data Analytics"),
    ],
    7: [
        ("ISE401", "DevOps"),
        ("ISE402", "Internet of Things"),
        ("ISE403", "Deep Learning"),
        ("ISE404", "Project Phase I"),
        ("ISE405", "Open Elective"),
    ],
    8: [
        ("ISE451", "Project Phase II"),
        ("ISE452", "Internship"),
        ("ISE453", "Cybersecurity Management"),
        ("ISE454", "Entrepreneurship"),
        ("ISE455", "Technical Seminar"),
    ],
}

GRADE_KEYWORDS = {
    "cgpa", "sgpa", "grade", "grades", "marks", "score", "percentage", "percent",
    "aggregate", "result", "performance",
}
CONTACT_KEYWORDS = {"contact", "phone", "mobile", "email", "whatsapp"}
BACKLOG_KEYWORDS = {"backlog", "backlogs", "arrear", "arrears"}
ATTENDANCE_KEYWORDS = {"attendance", "present", "absent", "shortage"}
MENTOR_KEYWORDS = {"mentor", "mentee", "guide"}
COURSE_KEYWORDS = {"course", "courses", "subject", "subjects", "enrolled", "enrollment"}
PROFILE_KEYWORDS = {"profile", "details", "student", "name", "usn", "semester", "department"}
DEFINITION_TERMS = (
    MENTOR_KEYWORDS
    | COURSE_KEYWORDS
    | ATTENDANCE_KEYWORDS
    | BACKLOG_KEYWORDS
    | GRADE_KEYWORDS
)
PERSONAL_TERMS = {"my", "me", "mine", "our", "us", "i"}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(str(value).strip()), 2)
    except (TypeError, ValueError):
        return default


def _normalise_usn(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalise_name(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _signature() -> tuple[str, float]:
    if not CSV_PATH.exists():
        return (str(CSV_PATH), 0)
    return (str(CSV_PATH), CSV_PATH.stat().st_mtime)


def _derive_attendance(student_id: int, cgpa: float, semester: int) -> float:
    base = 62 + (cgpa * 3.2)
    semester_adjust = (semester % 4) * 1.1
    id_adjust = (student_id % 9) - 4
    return round(max(50, min(98, base + semester_adjust + id_adjust)), 2)


def _derive_backlogs(cgpa: float) -> tuple[int, List[str]]:
    if cgpa < 5.5:
        return 3, ["DBMS", "OS", "CN"]
    if cgpa < 6.0:
        return 2, ["OS", "CN"]
    if cgpa < 6.8:
        return 1, ["DBMS"]
    return 0, []


def _mentor_for(student_id: int, semester: int) -> Dict[str, str]:
    return MENTORS[(student_id + semester) % len(MENTORS)]


def _courses_for(department: str, semester: int) -> List[Dict[str, Any]]:
    catalog = COURSE_CATALOG.get(semester) or COURSE_CATALOG.get(5, [])
    return [
        {
            "id": code,
            "shortname": code,
            "fullname": name,
            "department": department or "ISE",
            "semester": semester,
        }
        for code, name in catalog
    ]


def all_courses() -> List[Dict[str, Any]]:
    courses: List[Dict[str, Any]] = []
    for semester in sorted(COURSE_CATALOG):
        courses.extend(_courses_for("ISE", semester))
    return courses


def faculty_for_user(user_id: str) -> Optional[Dict[str, str]]:
    raw = (user_id or "").strip().upper()
    if not raw.startswith("FAC"):
        return None
    match = re.search(r"\d+", raw)
    number = int(match.group(0)) if match else 1
    mentor = MENTORS[(number - 1) % len(MENTORS)]
    return {
        "faculty_id": raw,
        "name": mentor["name"],
        "email": mentor["email"],
        "phone": mentor["phone"],
        "department": "ISE",
    }


def students_for_faculty(user_id: str) -> List[Dict[str, Any]]:
    faculty = faculty_for_user(user_id)
    if not faculty:
        return []
    return [
        student for student in load_students()
        if student["mentor"]["email"] == faculty["email"]
    ]


def faculty_profile(user_id: str) -> Optional[Dict[str, Any]]:
    faculty = faculty_for_user(user_id)
    if not faculty:
        return None
    students = students_for_faculty(user_id)
    courses = []
    seen_courses = set()
    for student in students:
        for course in student.get("courses", []):
            if course["id"] in seen_courses:
                continue
            seen_courses.add(course["id"])
            courses.append(course)
    avg_attendance = (
        round(sum(s["attendance_percent"] for s in students) / len(students), 2)
        if students else 0
    )
    avg_cgpa = (
        round(sum(s["cgpa"] for s in students) / len(students), 2)
        if students else 0
    )
    backlog_students = sum(1 for s in students if s["backlog_count"] > 0)
    profile = {
        **faculty,
        "courses": [course["fullname"] for course in courses[:8]],
        "course_details": courses,
        "sections": sorted({f"Semester {s['semester']}" for s in students}),
        "class_teacher_sections": sorted({f"Semester {s['semester']}" for s in students}),
        "student_count": len(students),
        "mentee_count": len(students),
        "avg_attendance": avg_attendance,
        "avg_cgpa": avg_cgpa,
        "backlog_students": backlog_students,
        "source": "students_500.csv",
    }
    return profile


def _clean_row(row: Dict[str, Any]) -> Dict[str, Any]:
    raw_usn = row.get("usn") or row.get("student_id") or row.get("username") or ""
    normalised_usn = _normalise_usn(raw_usn)
    # Source exports differ: one has numeric `id`, while the packaged CSV uses
    # `student_id` (USN).  A stable numeric fallback keeps derived demo fields
    # deterministic without discarding the provided academic values.
    student_id = _to_int(row.get("id"))
    if not student_id:
        digits = "".join(re.findall(r"\d+", normalised_usn))
        student_id = _to_int(digits)
    semester = _to_int(row.get("semester"))
    cgpa = _to_float(row.get("cgpa"))
    backlog_count = _to_int(row.get("backlog_count"), -1)
    if backlog_count < 0:
        backlog_count, backlog_courses = _derive_backlogs(cgpa)
    else:
        backlog_courses = [item.strip() for item in str(row.get("backlog_subjects") or "").split(",") if item.strip() and item.strip() != "0"]
    mentor = {
        "name": str(row.get("mentor_name") or "").strip(),
        "email": str(row.get("mentor_email") or "").strip(),
        "phone": str(row.get("mentor_phone") or "").strip(),
    }
    if not mentor["name"]:
        mentor = _mentor_for(student_id, semester)
    courses = _courses_for(str(row.get("department") or "ISE").strip(), semester)
    attendance_percent = _to_float(row.get("attendance_percent"), -1)
    if attendance_percent < 0:
        attendance_percent = _derive_attendance(student_id, cgpa, semester)
    total_sessions = 80
    present = round(total_sessions * attendance_percent / 100)
    absent = total_sessions - present

    return {
        "id": student_id,
        "student_id": normalised_usn,
        "usn": normalised_usn,
        "username": normalised_usn,
        "name": str(row.get("name") or "").strip(),
        "semester": semester,
        "cgpa": cgpa,
        "email": str(row.get("email") or row.get("college_email") or "").strip(),
        "phone": str(row.get("phone") or "").strip(),
        "batch": str(row.get("batch") or "").strip(),
        "department": str(row.get("department") or "").strip(),
        "course": str(row.get("department") or "ISE").strip(),
        "courses": courses,
        "enrolled_courses": courses,
        "course_count": len(courses),
        "attendance_percent": attendance_percent,
        "total_sessions": total_sessions,
        "present": present,
        "absent": absent,
        "late": 0,
        "excused": 0,
        "backlog_count": backlog_count,
        "backlog_courses": backlog_courses,
        "mentor": dict(mentor),
        "class_teacher": dict(mentor),
        "source": "students_500.csv",
    }


@lru_cache(maxsize=4)
def _load_students_cached(path_text: str, mtime: float) -> List[Dict[str, Any]]:
    # The CSV is an approved seed source; all runtime reads use SQLite.
    return [_clean_row(row) for row in fetch_records()]


def load_students() -> List[Dict[str, Any]]:
    return _load_students_cached(*_signature())


def student_count() -> int:
    return len(load_students())


def find_student(entity: str) -> Optional[Dict[str, Any]]:
    if not entity or str(entity).lower() == "general":
        return None
    text = str(entity).strip()
    usn_match = USN_RE.search(text)
    target_usn = _normalise_usn(usn_match.group(0) if usn_match else text)
    for student in load_students():
        if student["usn"] == target_usn:
            return student

    lowered = _normalise_name(text)
    query_tokens = set(re.findall(r"[a-z]+", lowered))
    best: tuple[int, Optional[Dict[str, Any]]] = (0, None)
    for student in load_students():
        name = _normalise_name(student.get("name"))
        if name and name in lowered:
            return student
        name_tokens = set(re.findall(r"[a-z]+", name))
        score = len(query_tokens & name_tokens)
        if score > best[0] and score >= 2:
            best = (score, student)
    return best[1]


def is_definition_query(query: str) -> bool:
    lowered = query.lower().strip()
    tokens = set(re.findall(r"[a-z0-9]+", lowered))
    has_definition_shape = (
        lowered.startswith(("what is ", "what are ", "define ", "explain "))
        or "meaning of" in lowered
    )
    if not has_definition_shape:
        return False
    if tokens & PERSONAL_TERMS:
        return False
    if find_student(query):
        return False
    # A conceptual question should take the LLM path even when it does not
    # mention one of the academic-data keywords. Personal questions (for
    # example, "Explain my attendance") are already excluded above.
    return True


def intent_from_query(query: str) -> Optional[str]:
    if is_definition_query(query):
        return None

    lowered = query.lower()
    tokens = set(re.findall(r"[a-z0-9]+", lowered))
    if "average cgpa" in lowered or "avg cgpa" in lowered:
        return "grades_average"
    if tokens & MENTOR_KEYWORDS:
        return "mentor_lookup"
    if tokens & ATTENDANCE_KEYWORDS:
        return "attendance_report"
    if tokens & COURSE_KEYWORDS:
        return "course_enrollment"
    if tokens & BACKLOG_KEYWORDS:
        return "backlog_report"
    if tokens & CONTACT_KEYWORDS:
        return "contact_lookup"
    if tokens & GRADE_KEYWORDS:
        return "student_profile"
    if tokens & PROFILE_KEYWORDS:
        return "student_profile"
    if "how many students" in lowered or "student count" in lowered:
        return "student_count"
    return None


def enrich_classification(query: str, classification: Dict[str, str], user_id: str = "") -> Dict[str, str]:
    enriched = dict(classification)
    if is_definition_query(query):
        enriched.update({
            "query_type": "general_query",
            "intent": "general",
            "entity": "general",
            "source": "definition_query",
        })
        return enriched

    query_student = find_student(query)
    requester = find_student(user_id)
    student = query_student or requester
    csv_intent = intent_from_query(query)

    if csv_intent == "student_count":
        enriched.update({
            "query_type": "organizational_query",
            "intent": "student_count",
            "entity": "general",
            "source": "csv_db",
        })
    elif student and csv_intent:
        enriched.update({
            "query_type": "organizational_query",
            "intent": csv_intent,
            "entity": student["usn"],
            "source": "csv_db",
            "matched_by": "query" if query_student else "requester_usn",
        })
    elif student and enriched.get("intent") in {"general", "", None}:
        enriched.update({
            "query_type": "organizational_query",
            "intent": "student_profile",
            "entity": student["usn"],
            "source": "csv_db",
            "matched_by": "query" if query_student else "requester_usn",
        })
    elif csv_intent:
        enriched.update({
            "query_type": "organizational_query",
            "intent": csv_intent,
            "entity": enriched.get("entity") or "general",
            "source": "csv_db",
        })

    return enriched


def user_context_for_student(student: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "role": "student",
        "user_id": student["usn"],
        "profile": dict(student),
        "overview": {
            "students": student_count(),
            "courses": [course["fullname"] for course in all_courses()],
        },
        "permissions": {
            "can_assign_mentor": False,
            "can_view_all_students": False,
        },
        "source": "students_500.csv",
    }


def default_context(user_id: str = "", role: str = "student") -> Dict[str, Any]:
    student = find_student(user_id)
    if student:
        return user_context_for_student(student)
    faculty = faculty_profile(user_id) if role == "faculty" else None
    if faculty:
        return {
            "role": "faculty",
            "user_id": user_id,
            "profile": faculty,
            "overview": {
                "students": faculty["student_count"],
                "courses": faculty["courses"],
            },
            "permissions": {
                "can_assign_mentor": True,
                "can_view_all_students": True,
            },
            "mentor_directory": MENTORS,
            "source": "students_500.csv",
        }
    return {
        "role": role,
        "user_id": user_id,
        "profile": None,
        "overview": {
            "students": student_count(),
            "courses": [course["fullname"] for course in all_courses()],
        },
        "permissions": {
            "can_assign_mentor": role in {"faculty", "admin"},
            "can_view_all_students": role in {"faculty", "admin"},
        },
        "source": "students_500.csv",
    }


def profile_summary(student: Dict[str, Any]) -> Dict[str, Any]:
    return dict(student)


def contact_summary(student: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "student_id": student["usn"],
        "name": student["name"],
        "student_contact": {
            "email": student["email"],
            "phone": student["phone"],
        },
        "source": "students_500.csv",
    }


def mentor_summary(student: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "student_id": student["usn"],
        "name": student["name"],
        "mentor": student["mentor"],
        "source": "students_500.csv",
    }


def attendance_summary(student: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "student_id": student["usn"],
        "student_name": student["name"],
        "course": student["department"],
        "attendance_percent": student["attendance_percent"],
        "total_sessions": student["total_sessions"],
        "present": student["present"],
        "absent": student["absent"],
        "late": student["late"],
        "excused": student["excused"],
        "student_count": 1,
        "source": "students_500.csv",
    }


def backlog_summary(student: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "count_with_backlogs": 1 if student["backlog_count"] else 0,
        "students": [{
            "student_id": student["usn"],
            "name": student["name"],
            "backlog_count": student["backlog_count"],
            "backlog_courses": student["backlog_courses"],
        }] if student["backlog_count"] else [],
        "source": "students_500.csv",
    }


def all_backlogs(limit: int = 30) -> Dict[str, Any]:
    students = [
        {
            "student_id": s["usn"],
            "name": s["name"],
            "backlog_count": s["backlog_count"],
            "backlog_courses": s["backlog_courses"],
        }
        for s in load_students()
        if s["backlog_count"] > 0
    ]
    return {
        "count_with_backlogs": len(students),
        "students": students[:limit],
        "source": "students_500.csv",
    }
