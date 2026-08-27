import unittest

from openpyxl import load_workbook

from response_formatter import create_excel


class ExcelExportTest(unittest.TestCase):
    def test_structured_records_use_a_data_sheet(self):
        path = create_excel("## Student report\nA concise summary.", [{"usn": "1NT23IS001", "name": "A Vaishnavi", "cgpa": 8.2}])
        try:
            workbook = load_workbook(path)
            self.assertIn("Data", workbook.sheetnames)
            sheet = workbook["Data"]
            self.assertEqual(sheet["A1"].value, "Usn")
            self.assertEqual(sheet["B2"].value, "A Vaishnavi")
            self.assertTrue(sheet.auto_filter.ref)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
