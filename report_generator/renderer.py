from pathlib import Path
import re
import tempfile

from jinja2 import Environment, FileSystemLoader, select_autoescape
import config
from .analytics import (
    calculate_financial_metrics,
    calculate_portfolio_metrics,
    calculate_project_metrics,
    calculate_sales,
    calculate_team_workload,
    identify_highlights,
    select_spotlight,
)
from .excel_parser import parse_workbook
from .narratives import (
    generate_executive_summary,
    generate_finance_insights,
    generate_project_commentary,
    generate_spotlight_summary,
    generate_team_insights,
)
from .normalization import format_money, period_label
from .risks import identify_risks
from .data_handling import handling_notes


def build_report_context(data):
    projects = calculate_project_metrics(data)
    kpis = calculate_portfolio_metrics(data, projects)
    team = calculate_team_workload(data)
    finance = calculate_financial_metrics(data) if config.SHOW_FINANCE or config.SHOW_SALES else {}
    sales = calculate_sales(data, projects, finance) if config.SHOW_SALES else []
    spotlight = select_spotlight(data, projects)
    highlights = identify_highlights(projects)
    risks = identify_risks(
        data, projects, team, spotlight, finance if config.SHOW_FINANCE else {}, sales
    )
    for project in projects:
        project["commentary"] = generate_project_commentary(project)
    if spotlight:
        spotlight["summary"] = generate_spotlight_summary(spotlight)
    actions = []
    seen = set()
    for risk in risks:
        identity = (risk.area, risk.action)
        if identity not in seen:
            actions.append({"priority": risk.severity, "area": risk.area, "action": risk.action})
            seen.add(identity)
    weekly = sorted(
        (p for p in projects if p["total"] and p["available"]),
        key=lambda p: (-p["completion_rate"], p["name"].casefold()),
    )
    mix = [
        ("Done", "done", "#2f7250"),
        ("In Progress", "in_progress", "#276b86"),
        ("In Review", "in_review", "#b78020"),
        ("On Hold / To Do", "hold_todo", "#8d96a0"),
    ]
    if kpis["unknown"]:
        mix.append(("Unknown", "unknown", "#765f84"))
    charts = {
        "projects": {
            "labels": [p["name"] for p in weekly],
            "values": [p["completion_rate"] for p in weekly],
        },
        "status": {
            "labels": [m[0] for m in mix],
            "values": [kpis[m[1]] for m in mix],
            "colors": [m[2] for m in mix],
        },
    }
    meta = {
        "company": config.COMPANY_NAME,
        "title": "Weekly Project & Sales Status Report",
        "report_start_date": data.report_start_date,
        "report_end_date": data.report_end_date,
        "report_period_label": period_label(data.report_start_date, data.report_end_date),
        "prepared_by": data.prepared_by or config.DEFAULT_PREPARED_BY or "Not available",
        "prepared_role": data.prepared_role or config.DEFAULT_ROLE,
        "source_file": data.source_file,
        "sources": data.sources,
        "task_detail_available": data.task_source_available,
    }
    return {
        "meta": meta,
        "kpis": kpis,
        "projects": projects,
        "tasks_by_project": {p["name"]: p["tasks"] for p in projects},
        "team": team,
        "team_insights": generate_team_insights(team),
        "spotlight": spotlight,
        "sales": sales,
        "finance": finance if config.SHOW_FINANCE else {},
        "finance_insights": generate_finance_insights(finance) if config.SHOW_FINANCE else [],
        "risks": risks,
        "actions": actions,
        "charts": charts,
        "chart_height": max(220, len(weekly) * 25),
        "show_charts": config.SHOW_CHARTS and bool(weekly),
        "weekly_chart_rows": weekly,
        "status_rows": [{"name": m[0], "count": kpis[m[1]]} for m in mix],
        "summary": generate_executive_summary(
            kpis, projects, team, highlights, finance if config.SHOW_FINANCE else {}, sales
        ),
        "warnings": list(data.warnings),
        "handling_notes": handling_notes(data, finance),
        "due_soon_days": config.DUE_SOON_DAYS,
    }


def safe_filename(context):
    meta = context["meta"]
    period = (
        f"{meta['report_start_date']}_to_{meta['report_end_date']}"
        if meta["report_start_date"] and meta["report_end_date"]
        else "period_unavailable"
    )
    prefix = (
        re.sub(r"[^A-Za-z0-9_-]+", "_", config.REPORT_FILE_PREFIX).strip("._-")[:60] or "Report"
    )
    return f"{prefix}_Weekly_Status_Report_{period}.html"


def generate_html(context):
    env = Environment(
        loader=FileSystemLoader(config.BASE_DIR / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["money"] = format_money
    env.filters["date_label"] = lambda value: value.strftime("%d %b %Y") if value else "—"
    env.filters["number"] = lambda value: (
        f"{value:,.2f}".rstrip("0").rstrip(".") if value is not None else "—"
    )
    env.filters["status_class"] = lambda value: {
        "Done": "done",
        "In Progress": "progress",
        "In Review": "review",
        "On Hold": "hold",
        "To Do": "todo",
        "Unknown": "unknown",
    }.get(value, "todo")
    css = (config.BASE_DIR / "static" / "report.css").read_text(encoding="utf-8")
    script = (config.BASE_DIR / "static" / "report.js").read_text(encoding="utf-8")
    chart_path = config.BASE_DIR / "static" / "vendor" / "chart.umd.js"
    chart_js = (
        chart_path.read_text(encoding="utf-8")
        if context["show_charts"] and chart_path.exists()
        else ""
    )
    # Only locally authored static assets are marked safe; every workbook value stays autoescaped.
    return env.get_template("weekly_report.html").render(
        **context, css=css, report_js=script, chart_js=chart_js
    )


def generate_report(workbook_path, output=None):
    data = parse_workbook(workbook_path)
    context = build_report_context(data)
    html = generate_html(context)
    destination = Path(output) if output else Path(config.OUTPUT_FOLDER) / safe_filename(context)
    if destination.suffix.casefold() != ".html":
        from .models import WorkbookError

        raise WorkbookError("The output filename must end in .html.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically so a failed generation cannot replace a usable report with a partial one.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tmp", dir=destination.parent, encoding="utf-8", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(html)
        temporary.replace(destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    return destination.resolve(), context
