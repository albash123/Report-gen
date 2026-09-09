"""Compact, factual notes about automatic source handling."""
from .normalization import STATUS_CORRECTIONS, key


def handling_notes(data, finance):
    notes = [
        "Task totals are calculated from available detail rows; duplicate IDs count once. Valid date columns take precedence over dates in status text. Missing invoice due dates use an explicitly labelled status date when available; otherwise dates remain Not available.",
    ]
    corrected = sum(key(t.raw_status) in STATUS_CORRECTIONS for t in [*data.tasks, *data.register])
    unassigned = sum(t.assignee == "Unassigned" for t in data.tasks)
    if corrected:
        notes.append(f"Automatically corrected {corrected} recognized status spelling error(s). Unrecognized statuses remain Unknown.")
    if unassigned:
        notes.append(f"Grouped {unassigned} task(s) without an assignee under Unassigned.")
    if finance:
        notes.append(f"Paid status overrides source buckets: {finance['reclassified_paid_count']} paid line(s) were removed from unpaid buckets. Financial totals use individual invoice amounts; differing source subtotals remain visible in the finance table.")
    if data.finance_stale or any(t.stale for t in data.tasks):
        notes.append("Carried-forward records are included and labelled as such; no newer status or receipt is assumed.")
    return notes
