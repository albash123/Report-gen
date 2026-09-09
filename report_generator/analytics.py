"""All report calculations operate on normalized records, independent of HTML."""

from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
import re

import config
from .models import ReportData
from .normalization import (
    clean_text,
    format_money,
    key,
    long_running_context,
    money_mentions,
    natural_key,
    normalize_date,
)

STATUSES = {
    "Done": "done",
    "In Progress": "in_progress",
    "In Review": "in_review",
    "On Hold": "on_hold",
    "To Do": "todo",
    "Unknown": "unknown",
}
FINANCE_CATEGORIES = (
    "Paid",
    "Due Soon",
    "Overdue / Collections",
    "Future Unpaid",
    "Pending Advances",
    "Unclassified",
)


def percentage(part, whole):
    return round(float(part / whole * 100), 1) if whole else 0.0


def task_metrics(tasks):
    counts = Counter(t.status for t in tasks)
    result = {field: counts[status] for status, field in STATUSES.items()}
    result.update(
        total=len(tasks), overdue=sum(t.overdue for t in tasks), stale=sum(t.stale for t in tasks)
    )
    result["hold_todo"] = result["on_hold"] + result["todo"]
    result["active"] = sum(result[k] for k in ("in_progress", "in_review", "on_hold", "todo"))
    result["completion_rate"] = percentage(result["done"], result["total"])
    result["overdue_rate"] = percentage(result["overdue"], result["total"])
    result["available"] = True
    return result


def summary_metrics(project):
    reported = project.reported_counts
    result = task_metrics([])
    if reported.get("total") is None:
        result["available"] = False
        return result
    result["total"] = int(reported["total"])
    for field in ("done", "in_progress", "in_review", "on_hold", "todo", "overdue"):
        result[field] = int(reported.get(field) or 0)
    result["hold_todo"] = int(reported.get("hold_todo") or result["on_hold"] + result["todo"])
    result["active"] = result["in_progress"] + result["in_review"] + result["hold_todo"]
    result["unknown"] = max(0, result["total"] - result["done"] - result["active"])
    result["completion_rate"] = percentage(result["done"], result["total"])
    result["overdue_rate"] = percentage(result["overdue"], result["total"])
    return result


def identify_overdue_tasks(tasks):
    return [t for t in tasks if t.overdue]


def classify_project(project, metrics, tasks):
    if project.stale:
        return "Carried-forward data"
    if project.overall_completion is not None and project.overall_completion >= 100:
        return "Completed / Ready for Close-Out"
    if not metrics["available"] or not metrics["total"]:
        return "No Current Data"
    context = project.notes + " " + " ".join(t.notes for t in tasks if t.status != "Done")
    if metrics["done"] == 0 and metrics["overdue"] and long_running_context(context):
        return "Stalled"
    if (
        metrics["overdue"] >= 2
        or (metrics["done"] == 0 and metrics["active"] >= 2)
        or metrics["on_hold"]
        and long_running_context(context)
    ):
        return "Needs Attention"
    if metrics["completion_rate"] >= 60 and metrics["overdue"] <= 1:
        return "On Track"
    if metrics["completion_rate"] < 40 or metrics["overdue"]:
        return "Needs Attention"
    return "Steady Progress"


def calculate_project_metrics(data: ReportData):
    projects = []
    for project in data.projects:
        tasks = [t for t in data.tasks if t.project == project.name]
        metrics = task_metrics(tasks) if data.task_source_available else summary_metrics(project)
        item = {
            "name": project.name,
            "overall_completion": project.overall_completion,
            "start_date": project.start_date,
            "end_date": project.end_date,
            "notes": project.notes,
            "stale": project.stale,
            "source": project.source,
            "tasks": tasks,
            **metrics,
        }
        item["status"] = classify_project(project, metrics, tasks)
        item["newly_onboarded"] = bool(
            re.search(
                r"(?:new (?:client |internal )?project onboarded|newly onboarded|onboarded this week)",
                project.notes + " " + " ".join(t.notes for t in tasks),
                re.I,
            )
        )
        item["newly_completed"] = bool(
            project.overall_completion == 100
            and any(
                t.status == "Done"
                and re.search(
                    r"project now 100|project has reached 100|project (?:completed|finished) this week|newly completed project",
                    t.notes + " " + project.notes,
                    re.I,
                )
                for t in tasks
            )
        )
        item["days_to_deadline"] = (
            (project.end_date - data.report_end_date).days
            if project.end_date and data.report_end_date
            else None
        )
        projects.append(item)
        if data.task_source_available:
            differences = []
            for field, reported in project.reported_counts.items():
                if reported is not None and field in metrics and int(reported) != metrics[field]:
                    differences.append(
                        f"{field.replace('_',' ')}: summary {reported}, task log {metrics[field]}"
                    )
            if differences:
                data.warn(
                    f"{project.name}: Executive Summary mismatch ({'; '.join(differences)}). Used task-log records."
                )
    return projects


def calculate_portfolio_metrics(data, projects=None):
    projects = projects if projects is not None else calculate_project_metrics(data)
    if data.task_source_available:
        result = task_metrics(data.tasks)
    else:
        result = task_metrics([])
        additive = (
            "total",
            "done",
            "in_progress",
            "in_review",
            "on_hold",
            "todo",
            "hold_todo",
            "active",
            "unknown",
            "overdue",
        )
        for field in additive:
            result[field] = sum(p[field] for p in projects if p["available"])
        result["completion_rate"] = percentage(result["done"], result["total"])
        result["overdue_rate"] = percentage(result["overdue"], result["total"])
        result["available"] = any(p["available"] for p in projects)
    result["total_projects"] = len(projects)
    result["projects_with_tasks"] = sum(p["total"] > 0 for p in projects)
    for field, reported in data.reported_totals.items():
        if (
            result["available"]
            and reported is not None
            and field in result
            and int(reported) != result[field]
        ):
            data.warn(
                f"Portfolio {field.replace('_',' ')}: Executive Summary total is {reported}; calculated from source records is {result[field]}. Source records take precedence."
            )
    return result


def calculate_team_workload(data):
    grouped = defaultdict(list)
    for task in data.tasks:
        grouped[task.assignee].append(task)
    named = [tasks for name, tasks in grouped.items() if name != "Unassigned"]
    average = sum(map(len, named)) / len(named) if named else 0
    project_owners = defaultdict(set)
    for task in data.tasks:
        if task.status != "Done":
            project_owners[task.project].add(task.assignee)
    result = []
    for name, tasks in grouped.items():
        metrics = task_metrics(tasks)
        sole = [p for p, owners in project_owners.items() if owners == {name}]
        signals = []
        if name != "Unassigned":
            if len(named) > 1 and metrics["total"] >= average * config.CAPACITY_LOAD_MULTIPLIER:
                signals.append(f"{metrics['total']} tasks versus a team average of {average:.1f}")
            if metrics["overdue"] >= 3:
                signals.append(f"{metrics['overdue']} overdue flags")
            if len(sole) >= 3:
                signals.append(f"sole owner of open work across {len(sole)} projects")
        result.append(
            {
                "name": name,
                **metrics,
                "project_count": len({t.project for t in tasks}),
                "sole_projects": sole,
                "capacity_signals": signals,
                "average_load": round(average, 1),
            }
        )
    return sorted(result, key=lambda r: (-r["total"], r["name"].casefold()))


def totals_by_currency(records):
    totals = defaultdict(Decimal)
    for record in records:
        if record.amount is not None:
            totals[record.currency] += record.amount
    return dict(sorted(totals.items()))


def invoice_category(invoice, report_end):
    # Individual payment state takes precedence over inherited section headings.
    if invoice.paid:
        return "Paid"
    if invoice.pending_advance:
        return "Pending Advances"
    if invoice.conditional_balance:
        return "Future Unpaid"
    if re.search(r"\b(?:overdue|collections|past due)\b", invoice.status, re.I):
        return "Overdue / Collections"
    if report_end and invoice.due_date:
        if invoice.due_date < report_end:
            return "Overdue / Collections"
        if invoice.due_date <= report_end + timedelta(days=config.DUE_SOON_DAYS):
            return "Due Soon"
        return "Future Unpaid"
    if invoice.section_category in ("Overdue / Collections", "Due Soon", "Future Unpaid"):
        return invoice.section_category
    return "Unclassified"


def calculate_financial_metrics(data):
    if not data.invoices:
        return {}
    categorized = {name: [] for name in FINANCE_CATEGORIES}
    rows = []
    for invoice in data.invoices:
        category = invoice_category(invoice, data.report_end_date)
        categorized[category].append(invoice)
        rows.append(
            {
                "record": invoice,
                "category": category,
                "amount_label": (
                    format_money({invoice.currency: invoice.amount})
                    if invoice.amount is not None
                    else "Not available"
                ),
                "days_overdue": (
                    max(0, (data.report_end_date - invoice.due_date).days)
                    if data.report_end_date
                    and invoice.due_date
                    and not invoice.paid
                    and not invoice.conditional_balance
                    else None
                ),
            }
        )
    controls = []
    for control in data.invoice_controls:
        lines = [i for i in data.invoices if i.source in control.sources]
        calculated = totals_by_currency(lines)
        notes_amounts = money_mentions(control.notes)
        mismatch = any(
            abs(calculated.get(c, Decimal(0)) - v) > Decimal("0.01")
            for c, v in control.amounts.items()
        )
        note_mismatch = bool(
            notes_amounts
            and any(
                c in calculated and abs(calculated[c] - v) > Decimal("0.01")
                for c, v in notes_amounts.items()
            )
        )
        incomplete = any(i.amount is None for i in lines)
        controls.append(
            {
                "label": control.label,
                "source": control.source,
                "stated": control.amounts,
                "calculated": calculated,
                "note_amounts": notes_amounts,
                "mismatch": mismatch or note_mismatch or incomplete,
                "notes": control.notes,
                "sources": control.sources,
            }
        )
        if mismatch or note_mismatch or incomplete:
            data.warn(
                f"Finance reconciliation required at {control.source}: {control.label}; line items {format_money(calculated)}, stated subtotal {format_money(control.amounts)}, note value {format_money(notes_amounts)}. Line amounts retained; agreement value needs confirmation."
            )
    sections = defaultdict(list)
    for invoice in data.invoices:
        sections[invoice.section].append(invoice)
    reconciliation = []
    for label, items in sections.items():
        remaining = [i for i in items if not i.paid]
        moved = sum(
            invoice_category(i, data.report_end_date) != i.section_category
            for i in items
            if i.section_category in FINANCE_CATEGORIES
        )
        reconciliation.append(
            {
                "label": label,
                "count": len(items),
                "line_total": totals_by_currency(items),
                "unpaid_total": totals_by_currency(remaining),
                "paid_count": sum(i.paid for i in items),
                "reclassified_count": moved,
            }
        )
    balances = totals_by_currency(i for i in data.invoices if not i.paid)
    return {
        "categories": [
            {"name": category, "count": len(items), "totals": totals_by_currency(items)}
            for category, items in categorized.items()
        ],
        "rows": rows,
        "controls": controls,
        "reconciliation": reconciliation,
        "outstanding": balances,
        "stale": data.finance_stale,
        "paid_count": len(categorized["Paid"]),
        "mismatch_count": sum(c["mismatch"] for c in controls),
        "reclassified_paid_count": sum(
            i.paid and i.section_category in ("Due Soon", "Overdue / Collections", "Future Unpaid")
            for i in data.invoices
        ),
        "pending_advances": totals_by_currency(categorized["Pending Advances"]),
        "pending_advance_count": len(categorized["Pending Advances"]),
        "unpriced_count": sum(i.amount is None for i in data.invoices),
    }


def register_metrics(tasks):
    counts = Counter(t.status for t in tasks)
    hours = defaultdict(Decimal)
    for task in tasks:
        if task.hours is not None:
            hours[task.status] += task.hours
    total = sum(hours.values(), Decimal(0))
    completed = hours["Done"]
    active = hours["In Progress"] + hours["In Review"]
    not_started = hours["To Do"]
    held = hours["On Hold"]
    unknown = hours["Unknown"]
    return {
        "total_tasks": len(tasks),
        "completed_tasks": counts["Done"],
        "active_tasks": counts["In Progress"] + counts["In Review"],
        "not_started_tasks": counts["To Do"],
        "held_tasks": counts["On Hold"],
        "unknown_tasks": counts["Unknown"],
        "total_hours": total,
        "completed_hours": completed,
        "active_hours": active,
        "not_started_hours": not_started,
        "held_hours": held,
        "unknown_hours": unknown,
        "other_hours": held + unknown,
        "remaining_hours": total - completed,
        "completed_hours_pct": percentage(completed, total),
        "active_hours_pct": percentage(active, total),
        "not_started_hours_pct": percentage(not_started, total),
        "held_hours_pct": percentage(held, total),
        "unknown_hours_pct": percentage(unknown, total),
        "remaining_hours_pct": percentage(total - completed, total),
        "hours_available": any(t.hours is not None for t in tasks),
        "missing_hours": sum(t.hours is None for t in tasks),
        "completion_rate": percentage(counts["Done"], len(tasks)),
    }


def analyze_project_register(data, project_name):
    tasks = [t for t in data.register if key(t.project) == key(project_name)]
    if not tasks:
        return {}
    result = register_metrics(tasks)
    for field in ("phase", "sprint", "month"):
        groups = defaultdict(list)
        for task in tasks:
            value = getattr(task, field)
            if value:
                groups[value].append(task)
        rows = []
        for label, items in groups.items():
            metrics = register_metrics(items)
            statuses = {t.status for t in items}
            state = (
                "Completed"
                if statuses == {"Done"}
                else (
                    "Not Started"
                    if statuses == {"To Do"}
                    else "Unknown" if statuses == {"Unknown"} else "Mixed / Open"
                )
            )
            rows.append({"name": label, **metrics, "state": state})
        result[field + "s"] = (
            sorted(rows, key=lambda r: natural_key(r["name"]))
            if field in ("sprint", "month")
            else rows
        )
    result["tasks"] = tasks
    for control in data.register_totals:
        if control["project"] and key(control["project"]) != key(project_name):
            continue
        if control["hours"] is not None and control["hours"] != result["total_hours"]:
            data.warn(
                f"Register hours mismatch for {project_name}: {control['source']} states {control['hours']} hours; detail rows sum to {result['total_hours']} hours."
            )
    return result


def select_spotlight(data, projects):
    if not projects:
        return {}
    chosen = next((p for p in projects if key(p["name"]) == key(config.SPOTLIGHT_PROJECT)), None)
    if chosen is None:
        active = [p for p in projects if p["active"] > 0]
        if not active:
            return {}
        chosen = max(active, key=lambda p: (p["active"], p["total"]))
    register = analyze_project_register(data, chosen["name"])
    return {"project": chosen, "register": register}


def lead_aging(days):
    if days is None or days < 0:
        return "Not available"
    if days <= 7:
        return "Recent"
    if days <= 14:
        return "Follow-up"
    if days <= 30:
        return "Aging"
    return "Stalled"


def sales_age(record, data):
    proposed = record.get("proposal_date")
    if re.search(
        r"\b(?:won|lost|closed|declined|withdrawn|cancelled|canceled)\b",
        record.get("stage", ""),
        re.I,
    ):
        record.update(days_waiting=None, aging="Closed")
        return record
    days = (data.report_end_date - proposed).days if data.report_end_date and proposed else None
    if days is not None and days < 0:
        data.warn(f"Future proposal date for {record['client']}. Days waiting is not available.")
        days = None
    record.update(days_waiting=days, aging=lead_aging(days))
    return record


def commercial_name(value):
    return key(re.sub(r"\b(?:pvt\.?|private|ltd\.?|limited|company)\b", "", value, flags=re.I))


def calculate_sales(data, projects, finance):
    sales = []
    for record in data.sales_records:
        sales.append(
            sales_age(
                {
                    **record,
                    "kind": "Pipeline",
                    "stated_value": {},
                    "reconciliation": False,
                    "related_projects": [],
                },
                data,
            )
        )
    groups = defaultdict(list)
    for invoice in data.invoices:
        if invoice.section_category == "Commercial agreements" or invoice.installment != "Invoice":
            groups[key(invoice.invoice_id) or invoice.source].append(invoice)
    for items in groups.values():
        clients = list(dict.fromkeys(i.client for i in items))
        controls = [
            c for c in finance.get("controls", []) if set(c["sources"]) & {i.source for i in items}
        ]
        related = [
            p
            for p in projects
            if any(commercial_name(p["name"]) == commercial_name(c) for c in clients)
        ]
        pending = any(i.pending_advance for i in items)
        agreement = {
            "client": " + ".join(clients),
            "opportunity": "Commercial agreement",
            "value": totals_by_currency(items),
            "stated_value": controls[0]["stated"] if len(controls) == 1 else {},
            "reconciliation": any(c["mismatch"] for c in controls),
            "stage": "Advance pending" if pending else "Agreement on file",
            "next_action": (
                "Confirm receipt of advance and reconcile agreement value."
                if pending
                else "Confirm remaining contractual milestones."
            ),
            "advance_status": "Pending" if pending else "Not available",
            "invoice_id": items[0].invoice_id,
            "proposal_date": None,
            "source": "; ".join(i.source for i in items),
            "notes": " ".join(c["notes"] for c in controls),
            "kind": "Agreement",
            "related_projects": [p["name"] for p in related],
            "delivery_started": any(
                p["done"] or p["in_progress"] or p["in_review"] for p in related
            ),
        }
        sales.append(sales_age(agreement, data))
    existing_clients = {commercial_name(r["client"]) for r in sales}
    for project in projects:
        context = (
            project["notes"] + " " + " ".join(t.title + " " + t.notes for t in project["tasks"])
        )
        if not re.search(r"proposal|sales lead|awaiting client feedback", context, re.I):
            continue
        if commercial_name(project["name"]) in existing_clients:
            continue
        sent = re.search(r"(?:proposal\s+(?:was\s+)?sent|sent)\s+([^;)]+)", context, re.I)
        proposed = normalize_date(sent[1], data.report_end_date, past=True) if sent else None
        matching = next(
            (t for t in project["tasks"] if re.search(r"proposal|client feedback", t.title, re.I)),
            None,
        )
        title = matching.title if matching else "Proposal / opportunity"
        action = "Follow up with the client and confirm whether the proposal remains active."
        value = money_mentions(project["notes"])
        sales.append(
            sales_age(
                {
                    "client": project["name"],
                    "opportunity": title,
                    "value": value,
                    "stated_value": {},
                    "reconciliation": False,
                    "stage": "Proposal / awaiting response",
                    "next_action": action,
                    "advance_status": "Not available",
                    "invoice_id": "",
                    "proposal_date": proposed,
                    "source": project["source"],
                    "notes": "",
                    "kind": "Lead",
                    "related_projects": [project["name"]],
                },
                data,
            )
        )
    return sales


def identify_highlights(projects):
    current = [p for p in projects if not p["stale"] and p["total"]]
    return {
        "strong": [p for p in current if p["completion_rate"] >= 80],
        "highest_output": (
            max(current, key=lambda p: p["done"]) if any(p["done"] for p in current) else None
        ),
        "newly_completed": [p for p in current if p["newly_completed"]],
        "newly_onboarded": [p for p in current if p["newly_onboarded"]],
        "low_movement": [
            p for p in current if p["done"] == 0 and (p["active"] >= 2 or p["overdue"])
        ],
    }
