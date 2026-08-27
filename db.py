"""
db.py

Database connection pool for the Moodle AI Assistant.
All other modules import `get_connection()` from here.

Reads config from environment variables (or .env via python-dotenv).
"""

import os
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "rootpass"),
    "database": os.getenv("DB_NAME", "moodledb"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
}


@contextmanager
def get_connection():
    """
    Context manager that yields a database connection.
    Auto-commits on success, rolls back on error, always closes.

    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM mdl_user LIMIT 5")
                rows = cur.fetchall()
    """
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def test_connection() -> dict:
    """Quick health check — returns row counts for key tables."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            tables = {
                "users": "mdl_user",
                "courses": "mdl_course",
                "enrolments": "mdl_user_enrolments",
                "grades": "mdl_grade_grades",
                "attendance_logs": "mdl_attendance_log",
            }
            counts = {}
            for label, table in tables.items():
                cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                counts[label] = cur.fetchone()["cnt"]
            return counts


if __name__ == "__main__":
    print("Testing database connection...")
    try:
        counts = test_connection()
        print("Connected! Row counts:")
        for label, count in counts.items():
            print(f"  {label:20s} {count:>8,}")
    except Exception as e:
        print(f"Connection failed: {e}")
