"""Centralized text, status, date, number and money interpretation."""

import calendar
import math
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import config

MISSING = {
    "",
    "-",
    "—",
    "n/a",
    "na",
    "none",
    "null",
    "tbd",
    "pending",
    "not available",
    "no date",
    "no date set",
}
STATUS_ALIASES = {
    "Done": ("done", "completed", "complete", "closed", "finished", "resolved"),
    "In Progress": ("in progress", "in-progress", "started", "active", "ongoing", "in process"),
    "In Review": (
        "in review",
        "review",
        "under review",
        "pending review",
        "awaiting review",
        "submitted",
    ),
    "On Hold": ("on hold", "hold", "blocked", "paused"),
    "To Do": ("to do", "todo", "not started", "not-started", "pending", "open", "backlog"),
}


def clean_text(value: Any) -> str:
    if value is None or isinstance(value, float) and math.isnan(value):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def key(value: Any) -> str:
    return re.sub(r"[^\w]+", "", clean_text(value).casefold().replace("&", " and "))


def normalize_name(value: Any) -> str:
    name = clean_text(value)
    aliases = {key(k): v for k, v in config.NAME_ALIASES.items()}
    return aliases.get(key(name), name) if name.casefold() not in MISSING else "Unassigned"


def normalize_project_name(value: Any) -> str:
    name = clean_text(value)
    aliases = {key(k): v for k, v in config.PROJECT_ALIASES.items()}
    return aliases.get(key(name), name) if name.casefold() not in MISSING else "Unspecified project"


def normalize_status(value: Any) -> str:
    normalized = key(value)
    for canonical, aliases in STATUS_ALIASES.items():
        if normalized in {key(a) for a in aliases}:
            return canonical
    return STATUS_CORRECTIONS.get(normalized, "Unknown")


# Explicit, conservative spelling corrections; unfamiliar statuses stay Unknown.
STATUS_CORRECTIONS = {
    "pendng": "To Do", "peding": "To Do", "pendding": "To Do",
    "complted": "Done", "compeleted": "Done", "compelete": "Done",
    "inprogess": "In Progress", "inprogres": "In Progress",
    "inreveiw": "In Review", "onhod": "On Hold",
}


def explicit_due_date(value, reference=None):
    match = re.search(r"\bdue\s*(?:date\s*)?[:=-]?\s*(.+)", clean_text(value), re.I)
    if not match or not DATE_TOKEN.match(match[1]):
        return None
    return normalize_date(DATE_TOKEN.match(match[1])[0], reference)


def safe_number(value: Any, default=None) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return default
    raw = clean_text(value).replace(",", "").replace(" ", "")
    raw = re.sub(r"^(?:[A-Z]{3}|[Rr][Ss]\.?|[$£€₨])", "", raw).rstrip("%")
    if raw.startswith("(") and raw.endswith(")"):
        raw = "-" + raw[1:-1]
    try:
        result = Decimal(raw)
        return result if result.is_finite() else default
    except InvalidOperation:
        return default


def normalize_currency(value: Any, amount: Any = None) -> str:
    raw = clean_text(value).upper()
    aliases = {
        "RS": "PKR",
        "RS.": "PKR",
        "₨": "PKR",
        "RUPEES": "PKR",
        "$": "USD",
        "US$": "USD",
        "€": "EUR",
        "£": "GBP",
    }
    if raw in aliases:
        return aliases[raw]
    if re.fullmatch(r"[A-Z]{3}", raw):
        return raw
    match = re.match(r"\s*([A-Za-z]{3}|US\$|Rs\.?|[$£€₨])", clean_text(amount))
    return normalize_currency(match[1]) if match else "Unspecified currency"


def normalize_percentage(value: Any, number_format: str = "") -> float | None:
    n = safe_number(value)
    if n is None:
        return None
    # Excel percentage cells store fractions. Plain 0..1 values follow that convention.
    if "%" not in clean_text(value) and ("%" in number_format or 0 <= n <= 1):
        n *= 100
    return float(n) if 0 <= n <= 100 else None


MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_TOKEN = re.compile(
    rf"\b(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}|"
    rf"{MONTH}[ .-]+\d{{1,2}}(?:(?:,?\s+|-)\d{{4}})?|\d{{1,2}}[ .-]+{MONTH}(?:(?:,?\s+|-)\d{{2,4}})?)\b",
    re.I,
)


def normalize_date(value: Any, reference: date | None = None, *, past: bool = False) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = clean_text(value)
    if raw.casefold() in MISSING:
        return None
    match = DATE_TOKEN.search(raw)
    if not match:
        return None
    token = re.sub(r"\bSept\b", "Sep", match[0], flags=re.I).replace(",", "")
    numeric = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", token)
    if numeric:
        first, second, year = map(int, numeric.groups())
        year = year + 2000 if year < 100 else year
        day, month = (first, second) if config.DAY_FIRST else (second, first)
        try:
            return date(year, month, day)
        except ValueError:
            return None
    has_year = bool(re.search(r"\b\d{4}\b|[A-Za-z]-\d{2}$", token))
    if not has_year and reference is None:
        return None
    candidate = token if has_year else f"{token} {reference.year}"
    candidate = re.sub(r"[.\s]+", " ", candidate)
    for fmt in (
        "%Y-%m-%d",
        "%b %d %Y",
        "%B %d %Y",
        "%d %b %Y",
        "%d %B %Y",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d-%b-%y",
        "%d-%B-%y",
        "%b-%d-%Y",
        "%B-%d-%Y",
        "%b-%d %Y",
        "%d-%b %Y",
    ):
        try:
            result = datetime.strptime(candidate, fmt).date()
            if not has_year and past and result > reference:
                result = result.replace(year=result.year - 1)
            return result
        except ValueError:
            continue
    return None


def reporting_period(value: Any) -> tuple[date | None, date | None]:
    raw = clean_text(value).split("|")[0].split("(Working")[0]
    tokens = DATE_TOKEN.findall(raw)
    if len(tokens) < 2:
        # A compact same-month period, e.g. September 4–10, 2027.
        match = re.search(
            rf"({MONTH})\s+(\d{{1,2}})\s*[–—-]\s*(\d{{1,2}}),?\s+(\d{{4}})", raw, re.I
        )
        if match:
            tokens = [f"{match[1]} {match[2]}, {match[4]}", f"{match[1]} {match[3]}, {match[4]}"]
    if len(tokens) < 2:
        return None, None
    year_match = re.search(r"\b(?:19|20)\d{2}\b", raw)
    ref = date(int(year_match[0]), 12, 31) if year_match else None
    start, end = normalize_date(tokens[0], ref), normalize_date(tokens[1], ref)
    if start and end and start > end:
        # Only infer cross-year rollover when the start's year was omitted.
        if not re.search(r"\b\d{4}\b", tokens[0]) and start.month > end.month:
            start = start.replace(year=start.year - 1)
        else:
            return None, None
    return start, end


def period_label(start: date | None, end: date | None) -> str:
    if not start or not end:
        return "Not available"
    if start.year == end.year:
        return f"{start:%b} {start.day} – {end:%b} {end.day}, {end.year}"
    return f"{start:%b} {start.day}, {start.year} – {end:%b} {end.day}, {end.year}"


def explicit_overdue(value: Any) -> bool:
    text = clean_text(value).casefold()
    text = re.sub(r"\b(?:not|no longer|never|no)\s+overdue\b|\b0\s+overdue\b", "", text)
    return bool(re.search(r"\boverdue\b|\bpast due\b", text))


def stale_context(value: Any) -> bool:
    return bool(
        re.search(
            r"no (?:new|fresh|current) data|no data this week|not (?:included|available).*?(?:export|data)|last (?:known|confirmed) status|status(?: shown)? (?:is |was )?carried forward|carried forward from (?:the )?last (?:confirmed|known)",
            clean_text(value),
            re.I,
        )
    )


def long_running_context(value: Any) -> bool:
    return bool(
        re.search(
            r"carry[- ]forward|carried forward|third\+? week|fourth|\d+(?:\.\d+)?\+? months?|no movement|no change from prior|unresolved|stuck|consecutive week",
            clean_text(value),
            re.I,
        )
    )


def is_paid(value: Any) -> bool:
    raw = clean_text(value).casefold()
    if re.search(
        r"\b(?:unpaid|not paid|partially paid|part paid|payment pending|pending payment)\b", raw
    ):
        return False
    return bool(re.search(r"\b(?:paid|settled|payment received)\b", raw))


def section_category(value: Any) -> str:
    raw = clean_text(value).casefold()
    if "commercial" in raw or "agreement" in raw or "advance" in raw:
        return "Commercial agreements"
    if "overdue" in raw or "collections" in raw:
        return "Overdue / Collections"
    if "upcoming" in raw or "due within" in raw or "due soon" in raw:
        return "Due Soon"
    if "unpaid" in raw or "future" in raw:
        return "Future Unpaid"
    if "paid" in raw or "payments" in raw:
        return "Paid"
    return "Unclassified"


def money_mentions(value: Any) -> dict[str, Decimal]:
    result = {}
    for currency, amount in re.findall(r"\b([A-Z]{3})\s+([\d,]+(?:\.\d+)?)", clean_text(value)):
        n = safe_number(amount)
        if n is not None:
            result[currency] = n
    return result


def format_money(values: dict) -> str:
    return (
        "; ".join(f"{currency} {amount:,.2f}" for currency, amount in sorted(values.items()))
        or "Not available"
    )


def natural_key(value: str):
    return tuple(
        (0, int(p)) if p.isdigit() else (1, p.casefold()) for p in re.split(r"(\d+)", value)
    )
