"""Stateless hosted upload flow: temporary input, direct response, no report store."""
from pathlib import Path
import tempfile
from flask import Flask, Response, jsonify, render_template_string, request
from werkzeug.exceptions import HTTPException
from report_generator.excel_parser import parse_workbook
from report_generator.models import WorkbookError
from report_generator.renderer import build_report_context, generate_html, safe_filename

PAGE = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Weekly Report Generator</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2f5f8;color:#162b3d;font:16px/1.6 system-ui,sans-serif}main{max-width:760px;margin:7vh auto;padding:40px;background:white;border-radius:18px;box-shadow:0 10px 45px #1232}h1{font-size:32px;line-height:1.2}small,.muted{color:#536575}label{display:block;margin:26px 0 8px}input{display:block;width:100%;padding:15px;border:1px solid #bac8d3;border-radius:8px}button,a.action{display:inline-block;background:#11667d;color:white;border:0;border-radius:8px;padding:12px 20px;font:inherit;text-decoration:none;cursor:pointer;margin:18px 8px 0 0}button:disabled{opacity:.6}#error{color:#a22525}#result{border-top:1px solid #dbe4ea;margin-top:24px;padding-top:12px}#filename{overflow-wrap:anywhere}@media(max-width:600px){main{margin:20px 12px;padding:24px}h1{font-size:27px}}</style></head><body><main>
<small>NEXUS · WEEKLY REPORTS</small><h1>Excel in. Management report out.</h1><p class="muted">Choose this week's workbook to generate a complete HTML report with charts, project updates and financial summaries.</p>
<form id="form"><label for="workbook"><strong>Weekly Excel workbook</strong> · .xlsx · up to 4 MB</label><input type="file" id="workbook" name="workbook" accept=".xlsx" required><button id="generate">Generate HTML Report</button></form>
<p id="status" role="status" aria-live="polite"></p><p id="error" role="alert"></p>
<section id="result" hidden><h2>Report generated successfully</h2><p id="filename"></p><a id="open" class="action" target="_blank" rel="noopener">Open Report</a><a id="download" class="action">Download HTML</a><p class="muted">Routine inconsistencies were handled automatically. Missing values and source differences are labelled in the report.</p></section>
<p class="muted"><small>Your workbook is processed on Vercel. The app deletes its temporary workbook after processing and returns the report directly to this browser. Download it before leaving this page. Downloaded HTML includes charts and styling and works offline.</small></p>
</main><script>
const form=document.querySelector('#form'),button=document.querySelector('#generate'),error=document.querySelector('#error'),statusText=document.querySelector('#status');let reportUrl=null;
form.addEventListener('submit',async event=>{event.preventDefault();error.textContent='';const file=document.querySelector('#workbook').files[0];if(!file)return;if(file.size>4*1024*1024){error.textContent='Choose a workbook smaller than 4 MB, or use the local generator for larger files.';return;}button.disabled=true;statusText.textContent='Reading workbook and generating report…';try{const response=await fetch('/generate',{method:'POST',headers:{'X-Report-Request':'1'},body:new FormData(form)});if(!response.ok){const info=await response.json().catch(()=>({error:'The report could not be generated. Try a smaller workbook.'}));throw Error(info.error);}const blob=await response.blob();if(reportUrl)URL.revokeObjectURL(reportUrl);reportUrl=URL.createObjectURL(blob);const name=response.headers.get('X-Report-Filename')||'Weekly_Report.html';document.querySelector('#open').href=reportUrl;const download=document.querySelector('#download');download.href=reportUrl;download.download=name;document.querySelector('#filename').textContent=name;document.querySelector('#result').hidden=false;statusText.textContent='Your report is ready.';}catch(e){error.textContent=e.message;statusText.textContent='';}finally{button.disabled=false;}});
</script></body></html>'''


def create_cloud_app():
    app = Flask(__name__, static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = 4 * 1024**2 + 65536

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @app.get('/')
    def index():
        return render_template_string(PAGE)

    @app.post('/generate')
    def generate():
        # Custom header prevents cross-origin HTML form submission; no CORS allowed.
        if request.headers.get('X-Report-Request') != '1':
            return jsonify(error='Open the upload page to generate a report.'), 403
        upload = request.files.get('workbook')
        if not upload or not upload.filename or not upload.filename.lower().endswith('.xlsx'):
            return jsonify(error='Please choose an .xlsx Excel workbook.'), 400
        try:
            with tempfile.TemporaryDirectory(prefix='report-') as directory:
                source = Path(directory) / 'workbook.xlsx'
                upload.save(source)
                if source.stat().st_size > 4 * 1024**2:
                    return jsonify(error='The workbook exceeds the 4 MB hosted upload limit.'), 413
                data = parse_workbook(source)
                data.source_file = Path(upload.filename.replace('\\', '/')).name
                context = build_report_context(data)
                html = generate_html(context).encode('utf-8')
                if len(html) > 4 * 1024**2:
                    return jsonify(error='This report is too large for hosted delivery. Use the local generator for this workbook.'), 413
            return Response(html, mimetype='text/html', headers={'X-Report-Filename': safe_filename(context)})
        except WorkbookError as exc:
            return jsonify(error=str(exc)), 400
        except Exception:
            # Do not write workbook content or source diagnostics to cloud logs.
            app.logger.error('Report generation failed')
            return jsonify(error='The workbook could not be processed. Check the workbook and try again.'), 500

    @app.errorhandler(HTTPException)
    def http_error(error):
        message = 'The workbook exceeds the 4 MB hosted upload limit.' if error.code == 413 else 'The requested page is unavailable.'
        return jsonify(error=message), error.code

    return app
