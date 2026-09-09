from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


class WorkbookError(ValueError):
    """An actionable validation error safe to display to the user."""


@dataclass
class Task:
    project: str
    task_id: str
    title: str
    status: str
    priority: str = ""
    assignee: str = "Unassigned"
    created_date: date | None = None
    due_date: date | None = None
    updated_date: date | None = None
    notes: str = ""
    overdue: bool = False
    stale: bool = False
    raw_status: str = ""
    source: str = ""


@dataclass
class Project:
    name: str
    overall_completion: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    notes: str = ""
    reported_counts: dict = field(default_factory=dict)
    stale: bool = False
    source: str = ""


@dataclass
class RegisterTask:
    project: str
    task_id: str
    title: str
    phase: str = "Not available"
    sprint: str = ""
    month: str = ""
    status: str = "Unknown"
    hours: Decimal | None = None
    assignee: str = "Unassigned"
    notes: str = ""
    raw_status: str = ""
    source: str = ""


@dataclass
class Invoice:
    client: str
    invoice_id: str
    amount: Decimal | None
    currency: str
    status: str
    section: str
    section_category: str = "Unclassified"
    due_date: date | None = None
    notes: str = ""
    installment: str = "Invoice"
    paid: bool = False
    pending_advance: bool = False
    conditional_balance: bool = False
    stale: bool = False
    source: str = ""


@dataclass
class InvoiceControl:
    label: str
    amounts: dict[str, Decimal]
    sources: list[str]
    notes: str = ""
    source: str = ""


@dataclass
class Risk:
    severity: str
    category: str
    area: str
    title: str
    explanation: str
    action: str


@dataclass
class ReportData:
    source_file: str = ""
    report_start_date: date | None = None
    report_end_date: date | None = None
    prepared_by: str = ""
    prepared_role: str = ""
    tasks: list[Task] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    invoice_controls: list[InvoiceControl] = field(default_factory=list)
    register: list[RegisterTask] = field(default_factory=list)
    register_totals: list[dict] = field(default_factory=list)
    reported_totals: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)
    task_source_available: bool = False
    finance_stale: bool = False
    sales_records: list[dict] = field(default_factory=list)

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)
