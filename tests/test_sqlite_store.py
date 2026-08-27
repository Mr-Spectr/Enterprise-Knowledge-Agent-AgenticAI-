import unittest

from academic_store import database_status, fetch_records


class SQLiteStoreTest(unittest.TestCase):
    def test_demo_data_is_available_through_sqlite(self):
        status = database_status()
        records = fetch_records()
        self.assertEqual(status["engine"], "sqlite")
        self.assertGreater(status["records"], 0)
        self.assertTrue(any(record.get("student_id") == "1NT23IS001" for record in records))


if __name__ == "__main__":
    unittest.main()
