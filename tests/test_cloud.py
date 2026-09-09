from io import BytesIO
import unittest
import openpyxl
from cloud import create_cloud_app


class CloudTests(unittest.TestCase):
    def test_direct_report_and_no_shared_session_required(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Detailed Task Log'
        ws.append(['Project', 'Task Title', 'Status'])
        ws.append(['Synthetic', 'Example task', 'pendng'])
        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)
        client = create_cloud_app().test_client()
        self.assertEqual(client.get('/').status_code, 200)
        response = client.post('/generate', headers={'X-Report-Request': '1'}, data={'workbook': (stream, 'example.xlsx')})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Example task', response.data)
        self.assertIn('X-Report-Filename', response.headers)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_invalid_and_cross_origin_form(self):
        client = create_cloud_app().test_client()
        self.assertEqual(client.post('/generate').status_code, 403)
        response = client.post('/generate',headers={'X-Report-Request':'1'},data={'workbook':(BytesIO(b'invalid'),'bad.xlsx')})
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)
