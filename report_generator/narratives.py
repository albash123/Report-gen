"""Deterministic narrative templates. No API calls, invented history or AI calculations."""

from .normalization import format_money


def generate_project_commentary(project):
    if project["stale"]:
        return "Latest available workbook status used; these records are carried forward."
    if not project["available"]:
        return "Weekly task counts are not available."
    if not project["total"]:
        return "No weekly task records were supplied."
    text = f"{project['done']} of {project['total']} tracked tasks closed ({project['completion_rate']:.1f}%)."
    if project["overdue"]:
        text += f" {project['overdue']} overdue flag(s) need follow-up."
    if project["status"].startswith("Completed"):
        text += " Overall completion is recorded as complete; confirm handover and close-out."
    return text


def generate_team_insights(team):
    named = [p for p in team if p["name"] != "Unassigned"]
    if not named:
        return []
    highest = named[0]
    results = [
        f"{highest['name']} carries the highest recorded workload: {highest['total']} tasks across {highest['project_count']} projects, with {highest['active']} open and {highest['overdue']} overdue."
    ]
    checks = [p["name"] for p in named if p["capacity_signals"]]
    if checks:
        results.append(
            "Capacity check recommended for "
            + ", ".join(checks)
            + " based on task concentration, overdue counts or sole ownership. Task volume does not establish overload."
        )
    return results


def generate_finance_insights(finance):
    if not finance:
        return []
    result = [
        f"Recorded unpaid line items total {format_money(finance['outstanding'])}, grouped by currency and excluding {finance['paid_count']} paid lines. This includes conditional balances and pending advances; it is not all immediately collectible."
    ]
    if finance["mismatch_count"]:
        result.append(
            f"Individual invoice lines are used for totals. {finance['mismatch_count']} source subtotal differences are shown below; the workbook does not establish a single agreed contract value."
        )
    if finance["stale"]:
        result.append(
            "Finance uses the latest available workbook records, marked as carried forward."
        )
    return result


def generate_spotlight_summary(spotlight):
    if not spotlight:
        return []
    project, register = spotlight["project"], spotlight["register"]
    paragraphs = [generate_project_commentary(project)]
    if register:
        paragraphs.append(
            f"The long-term register contains {register['total_tasks']} tasks: {register['completed_tasks']} completed, {register['active_tasks']} active, {register['not_started_tasks']} not started, {register['held_tasks']} held and {register['unknown_tasks']} with an unknown status."
        )
        if register["hours_available"]:
            paragraphs.append(
                f"Of {register['total_hours']:g} estimated hours, {register['completed_hours']:g} are completed ({register['completed_hours_pct']:.1f}%), {register['active_hours']:g} are active, {register['not_started_hours']:g} are not started, {register['held_hours']:g} are held and {register['unknown_hours']:g} are unclassified. This is estimated effort by status, not actual time spent."
            )
        if not project["end_date"]:
            paragraphs.append("Project deadline: not available in the workbook.")
    else:
        paragraphs.append(
            "No linked Task Register is available. Spotlight observations use the weekly task log."
        )
    return paragraphs


def generate_executive_summary(kpis, projects, team, highlights, finance, sales):
    if not kpis["available"]:
        paragraphs = [
            "The workbook supplies project information, but no usable weekly task counts. Weekly completion and workload cannot be assessed."
        ]
    else:
        rate = kpis["completion_rate"]
        assessment = (
            "Task closure was strong"
            if rate >= 70
            else (
                "The portfolio made steady progress"
                if rate >= 40
                else "Portfolio task closure was slow"
            )
        )
        if not kpis["total"]:
            assessment = "No weekly tasks were supplied"
        paragraphs = [
            f"{assessment}: {kpis['done']} of {kpis['total']} tracked tasks closed ({rate:.1f}%) across {kpis['projects_with_tasks']} projects with task records. The portfolio lists {kpis['total_projects']} projects in total. There are {kpis['active']} open tasks and {kpis['overdue']} overdue flags; overdue overlaps task status."
        ]
        if kpis["unknown"]:
            paragraphs[
                0
            ] += f" A further {kpis['unknown']} task(s) have an unrecognized or missing status."
        if kpis["stale"]:
            paragraphs[
                0
            ] += f" These figures include {kpis['stale']} carried-forward task record(s) from the available workbook."
    delivery = []
    top = highlights["highest_output"]
    if top:
        delivery.append(
            f"{top['name']} recorded the highest completion volume, closing {top['done']} of {top['total']} tracked tasks."
        )
    if highlights["strong"]:
        delivery.append(
            "Strong weekly closure (at least 80%) was recorded for "
            + ", ".join(p["name"] for p in highlights["strong"])
            + "."
        )
    if highlights["newly_completed"]:
        delivery.append(
            "The workbook indicates newly completed delivery for "
            + ", ".join(p["name"] for p in highlights["newly_completed"])
            + "; confirm close-out and handover."
        )
    if highlights["newly_onboarded"]:
        delivery.append(
            "Newly onboarded projects identified in source notes: "
            + ", ".join(p["name"] for p in highlights["newly_onboarded"])
            + "."
        )
    if delivery:
        paragraphs.append(" ".join(delivery))
    attention = []
    if highlights["low_movement"]:
        attention.append(
            "Projects with no closures and multiple open tasks or overdue work include "
            + ", ".join(p["name"] for p in highlights["low_movement"])
            + "."
        )
    reviews = [p for p in projects if not p["stale"] and p["in_review"] >= 3]
    if reviews:
        attention.append(
            "Review clearance needs attention on "
            + ", ".join(f"{p['name']} ({p['in_review']} items)" for p in reviews)
            + "."
        )
    if attention:
        paragraphs.append(" ".join(attention))
    team_text = generate_team_insights(team)
    if team_text:
        paragraphs.append(" ".join(team_text))
    commercial = generate_finance_insights(finance)
    aging = [
        r
        for r in sales
        if r["kind"] != "Agreement" and r["days_waiting"] is not None and r["days_waiting"] >= 15
    ]
    if aging:
        commercial.append(
            "Aging proposals requiring follow-up: "
            + ", ".join(f"{r['client']} ({r['days_waiting']} days)" for r in aging)
            + "."
        )
    if commercial:
        paragraphs.append(" ".join(commercial))
    return paragraphs
