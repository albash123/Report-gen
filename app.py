"""Minimal local upload app; uploaded source workbooks are deleted after processing."""

from pathlib import Path
import secrets
import tempfile
import threading
import webbrowser
from uuid import uuid4

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

import config
from report_generator.logging_setup import configure_logging
from report_generator.models import WorkbookError
from report_generator.renderer import generate_report


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secrets.token_hex(32),
        MAX_CONTENT_LENGTH=config.MAX_UPLOAD_MB * 1024**2,
        OUTPUT_FOLDER=str(config.OUTPUT_FOLDER),
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
    )
    if test_config:
        app.config.update(test_config)
    logger = configure_logging()
    output_root = Path(app.config["OUTPUT_FOLDER"])
    output_root.mkdir(parents=True, exist_ok=True)

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return render_template(
            "upload.html", csrf_token=session["csrf_token"], max_mb=config.MAX_UPLOAD_MB
        )

    @app.post("/generate")
    def generate():
        expected = session.get("csrf_token", "")
        if not expected or not secrets.compare_digest(request.form.get("csrf_token", ""), expected):
            return (
                render_template(
                    "upload.html",
                    error="The upload form expired. Reload the page and try again.",
                    max_mb=config.MAX_UPLOAD_MB,
                ),
                400,
            )
        upload = request.files.get("workbook")
        if not upload or not upload.filename:
            return (
                render_template(
                    "upload.html",
                    error="Please choose an .xlsx workbook.",
                    csrf_token=expected,
                    max_mb=config.MAX_UPLOAD_MB,
                ),
                400,
            )
        if Path(upload.filename).suffix.casefold() != ".xlsx":
            return (
                render_template(
                    "upload.html",
                    error="Please select an .xlsx Excel workbook.",
                    csrf_token=expected,
                    max_mb=config.MAX_UPLOAD_MB,
                ),
                400,
            )
        try:
            token = uuid4().hex
            with tempfile.TemporaryDirectory(prefix="weekly-report-") as temporary:
                source = Path(temporary) / "uploaded_workbook.xlsx"
                upload.save(source)
                from report_generator.excel_parser import parse_workbook
                from report_generator.renderer import (
                    build_report_context,
                    generate_html,
                    safe_filename,
                )

                data = parse_workbook(source)
                data.source_file = Path(upload.filename.replace("\\", "/")).name
                context = build_report_context(data)
                name = safe_filename(context)
                destination = output_root / token
                destination.mkdir()
                (destination / name).write_text(generate_html(context), encoding="utf-8")
            logger.info(
                "Generated upload report %s/%s; %s warnings", token, name, len(context["warnings"])
            )
            for diagnostic in context["warnings"]:
                logger.info("Source diagnostic: %s", diagnostic)
            return render_template(
                "upload.html",
                result={"token": token, "name": name},
                csrf_token=expected,
                max_mb=config.MAX_UPLOAD_MB,
            )
        except WorkbookError as exc:
            logger.exception("Workbook validation failed")
            return (
                render_template(
                    "upload.html", error=str(exc), csrf_token=expected, max_mb=config.MAX_UPLOAD_MB
                ),
                400,
            )
        except Exception:
            logger.exception("Upload report generation failed")
            return (
                render_template(
                    "upload.html",
                    error="The workbook could not be processed. Check that it is a readable Excel workbook and the output folder is writable. Technical details are in logs/report_generator.log.",
                    csrf_token=expected,
                    max_mb=config.MAX_UPLOAD_MB,
                ),
                500,
            )

    @app.get("/reports/<token>/<name>")
    def report(token, name):
        if (
            len(token) != 32
            or any(c not in "0123456789abcdef" for c in token)
            or not name.endswith(".html")
        ):
            abort(404)
        return send_from_directory(
            output_root / token,
            name,
            as_attachment=request.args.get("download") == "1",
            download_name=name,
            mimetype="text/html",
        )

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        return (
            render_template(
                "upload.html",
                error=f"The file exceeds the {config.MAX_UPLOAD_MB} MB upload limit. Choose a smaller workbook.",
                csrf_token=session.get("csrf_token", ""),
                max_mb=config.MAX_UPLOAD_MB,
            ),
            413,
        )

    @app.errorhandler(HTTPException)
    def http_error(error):
        return (
            render_template(
                "upload.html",
                error="That page or report could not be found. Open the upload page and try again.",
                csrf_token=session.get("csrf_token", ""),
                max_mb=config.MAX_UPLOAD_MB,
            ),
            error.code,
        )

    return app


if __name__ == "__main__":
    app = create_app()
    # Python's browser API opens only the requested local interface. No background services are installed.
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{config.PORT}")).start()
    print(f"Weekly Report Generator: http://127.0.0.1:{config.PORT}")
    print("Keep this terminal open. Press Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=config.PORT, debug=False, use_reloader=False)
