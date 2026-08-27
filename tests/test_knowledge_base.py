import tempfile
import unittest
from pathlib import Path

from knowledge_base import ingest_document, search_knowledge


class KnowledgeBaseTest(unittest.TestCase):
    def test_role_filter_precedes_search(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            public = root / "public.txt"
            faculty = root / "faculty.txt"
            public.write_text("Attendance policy requires documented absence.", encoding="utf-8")
            faculty.write_text("Faculty moderation meeting is confidential.", encoding="utf-8")
            db = root / "knowledge.db"
            ingest_document(public, "public", db)
            ingest_document(faculty, "faculty", db)
            self.assertEqual(search_knowledge("attendance policy", "student", db_path=db)["result_count"], 1)
            self.assertEqual(search_knowledge("moderation meeting", "student", db_path=db)["result_count"], 0)
            self.assertEqual(search_knowledge("moderation meeting", "faculty", db_path=db)["result_count"], 1)


if __name__ == "__main__":
    unittest.main()
