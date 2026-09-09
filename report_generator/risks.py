import re
import config
from .models import Risk
from .normalization import format_money, long_running_context


def identify_risks(data, projects, team, spotlight, finance, sales):
    risks = []

    def add(severity, category, area, title, explanation, action):
        risks.append(Risk(severity, category, area, title, explanation, action))

    for project in projects:
        name = project["name"]
        if project["stale"]:
            continue
        if project["status"] == "Stalled":
            context = project["notes"] + " ".join(t.notes for t in project["tasks"])
            multiple_weeks = bool(
                re.search(r"third|fourth|consecutive week|[3-9]\+? weeks|months", context, re.I)
            )
            severity = "HIGH" if multiple_weeks else "MEDIUM"
            add(
                severity,
                "Stalled Project",
                name,
                "No closures with overdue carry-forward work",
                f"No tasks closed from {project['total']} tracked tasks; {project['overdue']} are flagged overdue. Notes indicate carry-forward or lack of movement.",
                "Escalate open decisions and agree owners and dates for resolution.",
            )
        elif project["overdue"] >= 2:
            critical = sum(
                t.overdue and t.priority.casefold() in ("critical", "urgent", "high")
                for t in project["tasks"]
            )
            add(
                "HIGH" if critical >= 3 else "MEDIUM",
                "Overdue Tasks",
                name,
                "Overdue work needs follow-up",
                f"{project['overdue']} of {project['total']} tracked tasks are overdue; {critical} have high, urgent or critical priority.",
                "Review overdue items with owners and agree the next delivery or approval date.",
            )
        elif project["done"] == 0 and project["active"] >= 2:
            add(
                "MEDIUM",
                "Delivery Risk",
                name,
                "Low weekly movement",
                f"{project['active']} open tasks and no recorded closures in the supplied weekly log.",
                "Confirm priority, blockers and the next deliverable.",
            )
        review_overdue = sum(t.status == "In Review" and t.overdue for t in project["tasks"])
        if project["in_review"] >= 3 or review_overdue >= 2:
            add(
                "MEDIUM",
                "Review Bottleneck",
                name,
                "Review queue needs a clearance slot",
                f"{project['in_review']} items await review; {review_overdue} are overdue.",
                "Assign reviewers and schedule a standing review-clearance slot.",
            )
        held = [
            t
            for t in project["tasks"]
            if t.status == "On Hold"
            and (
                long_running_context(t.notes)
                or t.created_date
                and data.report_end_date
                and (data.report_end_date - t.created_date).days >= config.LONG_RUNNING_DAYS
            )
        ]
        if held:
            add(
                "MEDIUM",
                "Long-running On Hold Task",
                name,
                "Held work requires a decision",
                f"{len(held)} held item(s): "
                + "; ".join(f"{t.task_id or t.title} â€” {t.title}" for t in held)
                + ". Carry-forward notes or creation age indicate a long-running item; creation age does not prove time spent on hold.",
                "Confirm the blocker, accountable owner and restart or closure decision.",
            )
        days = project["days_to_deadline"]
        overall = project["overall_completion"]
        if days is not None and overall is not None and overall < 100:
            if 0 <= days <= 14 and overall < 80:
                add(
                    "HIGH",
                    "Timeline Risk",
                    name,
                    "Deadline approaching with substantial work remaining",
                    f"Recorded end date is {project['end_date']}; {days} days remain at the report cutoff. Overall completion is {overall:g}%.",
                    "Confirm scope, delivery capacity and the client milestone plan.",
                )
            elif days < 0:
                add(
                    "MEDIUM",
                    "Timeline Risk",
                    name,
                    "Recorded end date has passed",
                    f"The recorded end date is {abs(days)} days before the report cutoff and overall completion is {overall:g}%. The date may be an old contract milestone.",
                    "Verify the current milestone or extension before reporting a delivery delay.",
                )
        if overall == 100 and project["active"]:
            add(
                "MEDIUM",
                "Missing Data",
                name,
                "Completion and open tasks need reconciliation",
                f"Overall completion is 100%, but {project['active']} weekly tasks remain open.",
                "Confirm whether open work belongs to close-out, support or the delivery scope.",
            )
    for person in team:
        if person["capacity_signals"]:
            add(
                "MEDIUM",
                "Capacity Risk",
                person["name"],
                "Capacity check recommended",
                "; ".join(person["capacity_signals"])
                + ". Task counts do not measure effort or prove overload.",
                "Review estimates, priorities and review responsibilities before allocating more work.",
            )
    register = spotlight.get("register", {})
    if register:
        name = spotlight["project"]["name"]
        untouched = [
            p
            for p in register["phases"]
            if p["not_started_tasks"] and p["completed_tasks"] == 0 and p["active_tasks"] == 0
        ]
        if untouched:
            add(
                "MEDIUM",
                "Delivery Risk",
                name,
                "Register phases remain unstarted",
                "No completed or active work is recorded in: "
                + ", ".join(p["name"] for p in untouched)
                + ".",
                "Confirm phase sequencing and milestone dates against the current delivery plan.",
            )
        overall = spotlight["project"]["overall_completion"]
        if (
            register["hours_available"]
            and overall is not None
            and abs(overall - register["completed_hours_pct"]) >= 20
        ):
            add(
                "MEDIUM",
                "Missing Data",
                name,
                "Confirm completion measures and register freshness",
                f"Executive Summary overall completion is {overall:g}%; completed estimated register hours are {register['completed_hours_pct']:.1f}%. These measure different scopes and should be explained.",
                "Confirm the basis and freshness of overall completion and the detailed register.",
            )
    if finance:
        if finance["mismatch_count"]:
            add(
                "MEDIUM",
                "Finance Reconciliation",
                "Finance",
                "Source agreement totals differ",
                f"{finance['mismatch_count']} source subtotal differences remain. Calculations use individual invoice lines and exclude paid amounts.",
                "Verify contractual amounts before collecting disputed agreement balances.",
            )
        if finance["pending_advance_count"]:
            add(
                "MEDIUM",
                "Pending Advance",
                "Finance",
                "Advances remain recorded as pending",
                f"{finance['pending_advance_count']} advance lines total {format_money(finance['pending_advances'])}. Amounts follow recorded line items and may be disputed in reconciliation.",
                "Confirm receipts and whether work may proceed under the agreed payment terms.",
            )
        overdue = [
            r
            for r in finance["rows"]
            if r["category"] == "Overdue / Collections"
            and r["days_overdue"] is not None
            and r["days_overdue"] > 30
        ]
        if overdue:
            add(
                "MEDIUM",
                "Collections",
                "Finance",
                "Long-aged collections need follow-up",
                f"{len(overdue)} unpaid collection line(s) have recorded due dates more than 30 days before the report cutoff.",
                "Confirm current balances and agree collection follow-up with Finance.",
            )
    for lead in sales:
        if (
            lead["kind"] != "Agreement"
            and lead["days_waiting"] is not None
            and lead["days_waiting"] >= 15
        ):
            add(
                "MEDIUM",
                "Cold Lead",
                lead["client"],
                "Proposal follow-up required",
                f"{lead['days_waiting']} days since the recorded proposal date; aging category: {lead['aging']}.",
                lead["next_action"]
                or "Follow up and confirm whether the opportunity remains active.",
            )
    return sorted(
        risks,
        key=lambda r: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[r.severity], r.area.casefold(), r.title),
    )
