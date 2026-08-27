import unittest

from csv_db import find_student
from rbac import resolve_identity


class CsvIdentityTest(unittest.TestCase):
    def test_packaged_csv_schema_resolves_student_usn(self):
        student = find_student("1NT23IS015")
        self.assertIsNotNone(student)
        self.assertEqual(student["usn"], "1NT23IS015")
        self.assertEqual(resolve_identity("1NT23IS015").role, "student")


if __name__ == "__main__":
    unittest.main()
