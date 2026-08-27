import asyncio
import re
from typing import Dict

from csv_db import find_student, intent_from_query, is_definition_query


ALLOWED_INTENTS = {
    "student_count",
    "course_enrollment",
    "faculty_list",
    "grades_average",
    "attendance_report",
    "student_profile",
    "mentor_lookup",
    "class_teacher_info",
    "backlog_report",
    "contact_lookup",
    "general",
}


def _extract_entity(query: str) -> str:
    student = find_student(query)
    if student:
        return student["usn"]
    usn_match = re.search(r"\b\d[a-z0-9]{7,}\b", query, flags=re.IGNORECASE)
    if usn_match:
        return usn_match.group(0).upper()
    return "general"


def _heuristic_classify(query: str) -> Dict[str, str]:
    if is_definition_query(query):
        return {"query_type": "general_query", "intent": "general", "entity": "general"}

    lowered = query.lower()
    entity = _extract_entity(query)
    intent = intent_from_query(query)

    if any(phrase in lowered for phrase in ["teaching profile", "my teaching profile", "show my teaching"]):
        intent = "student_profile"
    elif any(phrase in lowered for phrase in ["my students", "list my students", "mentees", "my mentees"]):
        intent = "course_enrollment"
    elif "my course" in lowered or "my courses" in lowered:
        intent = "course_enrollment"
    elif "average cgpa" in lowered or "avg cgpa" in lowered:
        intent = "grades_average"

    if not intent:
        if any(word in lowered for word in ["class teacher", "homeroom", "ct info"]):
            intent = "class_teacher_info"
        elif any(word in lowered for word in ["faculty", "professor", "teacher list", "who teaches", "instructor"]):
            intent = "faculty_list"
        elif any(word in lowered for word in ["enrollment", "enrolled", "list students", "students in"]):
            intent = "course_enrollment"
        else:
            intent = "general"

    org_terms = [
        "student", "grade", "marks", "cgpa", "attendance", "faculty", "course",
        "mentor", "class teacher", "backlog", "usn", "semester", "enrollment",
        "whatsapp", "contact", "phone", "email",
    ]
    query_type = (
        "organizational_query"
        if any(term in lowered for term in org_terms) or entity != "general" or intent != "general"
        else "general_query"
    )
    return {"query_type": query_type, "intent": intent, "entity": entity}


async def classify_query(query: str) -> Dict[str, str]:
    return await asyncio.to_thread(_heuristic_classify, query)
