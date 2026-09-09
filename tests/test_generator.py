import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import openpyxl
from report_generator.normalization import normalize_status, explicit_due_date
from report_generator.renderer import generate_report


class GeneratorTests(unittest.TestCase):
    def test_conservative_cleanup(self):
        self.assertEqual(normalize_status('pendng'), 'To Do')
        self.assertEqual(normalize_status('unfamiliar'), 'Unknown')
        self.assertEqual(explicit_due_date('Issued 2026-08-01; Due: 2026-09-18'), date(2026, 9, 18))
        self.assertIsNone(explicit_due_date('Due unknown; issued 2026-08-01'))

    def test_synthetic_workbook_generates_portable_report(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Detailed Task Log'
        ws.append(['Reporting Period: Sep 4, 2026 to Sep 10, 2026'])
        ws.append(['Project', 'Task ID', 'Task Title', 'Status', 'Assignee'])
        ws.append(['Example Project', '1', '<script>alert(1)</script>', 'pendng', None])
        with TemporaryDirectory() as temp:
            source = Path(temp) / 'sample.xlsx'
            wb.save(source)
            output, context = generate_report(source, Path(temp) / 'report.html')
            html = output.read_text(encoding='utf-8')
        self.assertIn('Unassigned', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertTrue(any('1 recognized status' in n for n in context['handling_notes']))
