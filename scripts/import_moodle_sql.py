"""Import a Moodle MySQL dump into the app's normalized SQLite data store.

Usage: python scripts/import_moodle_sql.py path/to/moodle_slim.sql --out data/moodle.sqlite
The raw Moodle dump is never copied into this repository.
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

TARGETS = {"mdl_user", "mdl_course", "mdl_enrol", "mdl_user_enrolments", "mdl_grade_items", "mdl_grade_grades", "mdl_attendance_log", "mdl_attendance_statuses"}
USN = re.compile(r"^\dnt\d{2}[a-z]{2}\d{3}$", re.I)


def values(statement: str):
    payload = statement[statement.find("VALUES") + 6:].rstrip().rstrip(";")
    depth = 0; quoted = False; escaped = False; start = 0
    for index, char in enumerate(payload):
        if quoted:
            if escaped: escaped = False
            elif char == "\\": escaped = True
            elif char == "'": quoted = False
        elif char == "'": quoted = True
        elif char == "(":
            if depth == 0: start = index + 1
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                row = next(csv.reader([payload[start:index]], quotechar="'", escapechar="\\"))
                yield [None if field == "NULL" else field for field in row]


def dump_rows(path: Path):
    current = None; buffer: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as source:
        for line in source:
            match = re.match(r"INSERT INTO `(mdl_[^`]+)` VALUES", line)
            if match and match.group(1) in TARGETS:
                current = match.group(1); buffer = [line]
                # Small Moodle tables may be emitted as a one-line INSERT.
                if line.rstrip().endswith(";"):
                    yield current, list(values("".join(buffer)))
                    current = None; buffer = []
                continue
            if current:
                buffer.append(line)
                if line.rstrip().endswith(";"):
                    yield current, list(values("".join(buffer)))
                    current = None; buffer = []


def number(value, default=0.0):
    try: return float(value)
    except (TypeError, ValueError): return default


def main(source_path: Path, output_path: Path):
    tables = defaultdict(list)
    for table, rows in dump_rows(source_path):
        tables[table].extend(rows)

    courses = {int(row[0]): row for row in tables["mdl_course"] if row and row[0]}
    # Moodle's enrol table stores its course reference at column 3, while
    # user_enrolments stores enrolid/userid at columns 2 and 3 respectively.
    enrol_course = {int(row[0]): int(row[3]) for row in tables["mdl_enrol"] if len(row) > 3 and row[0] and row[3]}
    courses_by_user = defaultdict(list)
    for row in tables["mdl_user_enrolments"]:
        if len(row) > 3 and row[3] and row[2] and int(row[2]) in enrol_course:
            courses_by_user[int(row[3])].append(enrol_course[int(row[2])])
    grade_items = {int(row[0]): row for row in tables["mdl_grade_items"] if row and row[0]}
    grades = defaultdict(list)
    for row in tables["mdl_grade_grades"]:
        if len(row) > 8 and row[2] and row[1] and row[8] is not None:
            item = grade_items.get(int(row[1]))
            if item and len(item) > 12 and item[4] == "course":
                maximum = number(item[12] if len(item) > 12 else 100, 100)
                if maximum: grades[int(row[2])].append(number(row[8]) / maximum * 100)
    present_statuses = {int(row[0]) for row in tables["mdl_attendance_statuses"] if len(row) > 2 and row[0] and str(row[2]).upper() in {"P", "L", "E"}}
    attendance = defaultdict(lambda: [0, 0])
    for row in tables["mdl_attendance_log"]:
        if len(row) > 3 and row[2]:
            bucket = attendance[int(row[2])]; bucket[0] += 1; bucket[1] += int(row[3] in present_statuses)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_path) as conn:
        conn.execute("DROP TABLE IF EXISTS student_records")
        conn.execute("""CREATE TABLE student_records (
          student_id TEXT, name TEXT, semester TEXT, department TEXT, course TEXT,
          cgpa TEXT, attendance_percent TEXT, backlog_count TEXT, backlog_subjects TEXT,
          mentor_name TEXT, mentor_email TEXT, mentor_phone TEXT, phone TEXT,
          college_email TEXT, personal_email TEXT, faculty TEXT, faculty_id TEXT)""")
        rows = []
        for user in tables["mdl_user"]:
            if len(user) < 18 or user[4] == "1" or user[5] == "1": continue
            identifier = (user[9] or "").strip().upper()
            if not USN.match(identifier): continue
            uid = int(user[0]); enrolled = [courses[c] for c in courses_by_user[uid] if c in courses]
            course_names = "; ".join(str(course[3] or course[2] or "") for course in enrolled[:8])
            average = sum(grades[uid]) / len(grades[uid]) if grades[uid] else 0
            total, present = attendance[uid]
            attendance_percent = round(present * 100 / total, 2) if total else 0
            # Moodle does not expose an authoritative "backlog" field in this
            # dump. Leave it blank rather than inventing a value.
            rows.append((identifier, f"{user[10] or ''} {user[11] or ''}".strip(), "", user[17] or "", course_names or "", round(average / 10, 2) if grades[uid] else "", attendance_percent if total else "", "", "", "", "", "", user[14] or "", user[12] or "", "", "", ""))
        conn.executemany("INSERT INTO student_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        conn.execute("CREATE INDEX idx_student_records_id ON student_records(student_id)")
    print({"output": str(output_path), "students": len(rows), "courses": len(courses), "attendance_logs": len(tables['mdl_attendance_log'])})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/moodle.sqlite"))
    args = parser.parse_args()
    main(args.dump, args.out)
