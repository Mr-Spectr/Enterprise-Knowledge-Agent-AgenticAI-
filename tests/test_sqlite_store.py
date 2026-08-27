import sqlite3
import unittest

from academic_store import database_status, fetch_records


class SQLiteStoreTest(unittest.TestCase):
    def test_demo_data_is_available_through_sqlite(self):
        status = database_status()
        records = fetch_records()
        self.assertEqual(status["engine"], "sqlite")
        self.assertGreater(status["records"], 0)
        self.assertTrue(any(record.get("student_id") == "1NT23IS001" for record in records))

    def test_imported_records_have_unique_ids_and_provenance_fields(self):
        status = database_status()
        if status["source"] != "external_sqlite":
            self.skipTest("Moodle import is not configured for this test run")
        with sqlite3.connect(status["path"]) as conn:
            duplicates = conn.execute(
                "SELECT COUNT(*) FROM (SELECT student_id FROM student_records GROUP BY student_id HAVING COUNT(*) > 1)"
            ).fetchone()[0]
            assigned = conn.execute(
                "SELECT COUNT(*) FROM student_records WHERE mentor_name NOT IN ('', 'Not assigned')"
            ).fetchone()[0]
        self.assertEqual(duplicates, 0)
        self.assertEqual(assigned, status["records"])


if __name__ == "__main__":
    unittest.main()
