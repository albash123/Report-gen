# Weekly Report Generator

A local Excel-to-HTML management report generator. Select a new weekly `.xlsx`, click **Generate HTML Report**, then open or download a portable report. No weekly Python, HTML or JavaScript edits are needed. No AI account, API key, database or hosting is required.

The generator reads all available projects and people from the workbook, calculates task, project, team, register and finance metrics, and writes rule-based commentary, risks and actions. Both Chart.js charts, CSS and JavaScript are embedded in the final HTML. The downloaded report works offline in Chrome or Edge.

## Installation

Requires Python **3.10 or newer**. Python 3.12 was used for acceptance testing. Install Python from [python.org](https://www.python.org/downloads/) if needed, including its launcher / PATH option.

On Windows, extract the project and double-click **`Setup_Windows.cmd`** once. Then use **`Start_Report_Generator.cmd`** each week. Setup needs internet to install the three Python dependencies; report generation thereafter works locally and offline.

Or install manually from the project directory:

```bash
python -m venv .venv
```

Windows Command Prompt:

```bat
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Windows PowerShell, without changing execution policy:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The browser opens [the local upload page](http://127.0.0.1:5000). If it does not open automatically, visit that address. The application binds only to this computer. Change `PORT` in `config.py` once if that port is already in use.

## Command line

With the virtual environment activated:

```bash
python generate_report.py my_weekly_report.xlsx
python generate_report.py my_weekly_report.xlsx --output report.html
```

On Windows, activation is optional:

```powershell
.\.venv\Scripts\python.exe generate_report.py "C:\Reports\next_week.xlsx"
```

The CLI creates `output/` automatically and names the report from the detected reporting period:

```text
Nexus_Weekly_Status_Report_<start-date>_to_<end-date>.html
```

Missing periods use `period_unavailable` and create a warning. The CLI replaces the same output filename atomically when rerun. Use `--output` to retain multiple versions. Web uploads save into separate generated subfolders of `output/`, so uploads for the same week do not overwrite one another. The download retains the date-based filename.

The CLI returns exit code 0 on success, 2 for workbook validation errors, and 1 for other errors. Warnings do not block generation. Technical errors are logged to `logs/report_generator.log` with rotating log files. Normal users see readable messages rather than Python tracebacks.

## Next week's workflow

Export or fill in the next weekly workbook using the same kinds of sheets and column labels. Update the reporting-period label in the workbook itself. Add or remove project/task rows and assignees as usual. The generator discovers them on every run.

There is no application step for entering counts, dates, employee names, percentages, charts, invoice amounts, risks or summaries. Upload the new workbook, generate, and save the HTML. Only data-quality corrections should be made in Excel; the generated report does not repair the source workbook.

## Input contract and discovery

Sheet order, header row positions, blank spacer rows and minor header spelling/spacing differences can change. The parser normalizes header labels and locates sections by content. The minimum input is a recognized weekly task table or project summary. An empty recognized task table is handled as zero tasks.

| Source | Minimum recognizable columns | Purpose |
| --- | --- | --- |
| Detailed Task Log or equivalent | Project, Task Title, Status | Authoritative weekly tasks, assignees and overdue flags |
| Executive Summary or equivalent | Project and either Completion % or Total Tasks | Overall project completion, dates, project notes and control counts |
| Project Breakdown | Project section headings plus Task ID, Title, Status | Redundant source check; fallback weekly task source if the main log is unusable |
| Invoice Summary or equivalent | Client, Amount, Status | Invoice records, categories, subtotal checks and commercial agreements |
| Task Register or equivalent | Task / Deliverable, Phase, Status | Long-term estimated effort and phase/sprint progress |
| Optional sales table | Client, Opportunity | Explicit leads, values, stages, proposal dates and next actions |

Examples of aliases: `TaskID` / `ID` → Task ID; `Title` / `Task / Deliverable` → task title; `Assigned To` / `Owner` → assignee; `Deadline` → due date; `Customer` → client. See `COLUMN_ALIASES` in `report_generator/excel_parser.py` for the complete supported set. When a genuinely new export format introduces different labels, aliases can be extended once.

Invoice Summary, Task Register and Project Breakdown are optional. Missing optional sources do not block generation. Sales and finance sections are omitted if there are no records. If only a project summary is usable, the report labels any available summary counts and does not fabricate detailed tasks or team workload. A malformed optional sheet is not used as a source for invented values.

Project Breakdown headings should identify a project before a repeated task table, for example `PROJECT NAME | X/Y tasks completed this week`. Task Register should have a Project column or a heading containing a known project name. A register is never assigned to the spotlight merely because it exists. An unidentifiable register is flagged; a stable sheet-to-project mapping can be set in `REGISTER_PROJECTS` once.

## Calculation and interpretation rules

### Weekly metrics

- All supplied weekly task rows are in scope. Created dates do not filter the list: a workbook can deliberately carry tasks or just-after-cutoff closures into this reporting cycle.
- Status aliases are centralized. Done/completed/closed normalize to Done; Started and In Progress normalize to In Progress; Not Started and Pending normalize to To Do. Recognized spelling errors such as pendng are corrected automatically. Unfamiliar values remain Unknown. Source diagnostics are logged; the report shows compact data-handling notes.
- Completion = Done ÷ total tasks. Zero tasks gives 0% at portfolio level. A project with no tasks has no applicable weekly percentage in the ledger.
- Open / active = In Progress + In Review + On Hold + To Do. Unknown tasks are shown separately; they are not silently included in a known status.
- Overdue is an overlapping flag: an explicit overdue note or affirmative flag, or a due date before the report cutoff for a task not marked Done. A completed task is flagged only if the source explicitly still marks an overdue issue. Negated notes such as `Not overdue` do not trigger the flag.
- Explicitly stale project data is included in source counts and clearly identified. A task carried forward during ordinary ongoing delivery does not, by itself, make a whole project stale.
- Task IDs are unique within the weekly population. Duplicate IDs count once: latest available update date, then most complete row, then last row. All duplicates are flagged. Rows without IDs remain separate because identity cannot be established safely.
- Case, spacing, punctuation and `&` versus `and` are normalized for project matching. Employee name capitalization/spacing variants are merged. Different names are not guessed to be the same person.
- Overall completion comes from Executive Summary, never from weekly completion. Numeric fractions, percentages and Excel percent formats are supported.

### Reporting dates

Explicit Reporting Period labels take priority; task-log headings are a fallback. ISO, day-month-year and English month-name ranges are supported, including same-month and cross-year ranges. No missing period is replaced with today's date.

Native Excel dates retain their exact stored values. Numeric text dates use `DAY_FIRST = True` by default. Yearless Created / proposal dates use the most recent matching date at or before the report end; yearless due dates use the report-end year. Provide years at year boundaries when a different interpretation is intended. Missing or malformed dates stay unavailable. Notes claiming elapsed days do not replace a calculable date-based age.

Excel formula cells use Excel's saved results. Python does not execute workbook formulas. Missing cached results are warned about, and affected fields remain unavailable; task counts, detail totals and other analytics are calculated afresh in Python. Recalculate and save the workbook in Excel or LibreOffice to refresh missing formula results. Source totals are control checks, not substitutes for fresh detail calculations.

### Finance and sales

All money is summed with `Decimal` and grouped by currency. No exchange-rate conversion takes place. Missing amounts are excluded and recorded in source diagnostics; missing currencies remain a separate unspecified-currency group.

Payment status on an invoice line takes precedence over a source section. Paid lines are excluded from unpaid exposure even when they remain under an overdue or upcoming heading. Partial or pending payment text does not mean fully Paid. Where partial receipts are not separately provided, the full recorded line remains provisional; the generator cannot infer a residual balance.

Classification order is Paid → Pending Advance → balance conditional on completion → explicit Collections/Overdue → due-date comparison → available source category → Unclassified. Due Soon is due at the report cutoff through the configured following 30 days. Explicit Collections remains collections even if its due date is in the future. Due Date columns take precedence over contradictory dates in status text, with a warning.

The finance table shows original section line totals alongside remaining unpaid lines. Cards separately reclassify lines at the report date. Future buckets can move into Due Soon as the report period advances. Source commercial subtotals and amounts stated in notes are compared with line sums; conflicting amounts remain visible and require reconciliation. Disputed installment values are included as recorded line amounts, not silently replaced with a guessed agreement value.

Shared invoice numbers do not collapse legitimate client-specific advance and balance lines. Exact duplicate lines are ignored and flagged. Commercial opportunities group those lines by invoice number. Source proposal notes and optional explicit pipeline tables supply leads; no unsupported client names or deal amounts are invented. Sales aging is Recent (0–7 days), Follow-up (8–14), Aging (15–30), or Stalled (over 30).

### Spotlight, narrative and risks

The configured spotlight is used when present. Otherwise, the project with the most active weekly tasks is selected. Without a linked register, the spotlight uses weekly task data only.

Register completion is based on completed estimated hours, not time spent. Active, not-started, held and unknown-status hours partition the remaining effort. Missing estimates are flagged. Phase names and sprint labels are discovered from the register. Sprint ranges are retained as groups, so a task's hours are never duplicated across individual sprints. A mixed group is not described as wholly completed.

Executive wording is deterministic: at least 70% weekly closure is strong, 40–69.9% is steady, and below 40% is slow. Projects at 80% or above are strong weekly performers. Project statuses consider stale data, overall completion, closure, overdue items and carry-forward context. Rule ordering and thresholds are visible in `analytics.py` and `risks.py`.

Capacity checks compare task volumes, overdue counts and sole ownership. They do not claim anyone is definitely overloaded. Deadline risks require a recorded project end date. A single workbook cannot establish a historic best week, a trend, an unstated contract duration or a new deadline. Those claims are not generated.

## Configuration

`config.py` separates organization metadata from weekly data:

| Option | Purpose |
| --- | --- |
| COMPANY_NAME / REPORT_FILE_PREFIX | Organization and safe output prefix |
| DEFAULT_PREPARED_BY / DEFAULT_ROLE | Used when workbook metadata is missing |
| SPOTLIGHT_PROJECT | Preferred spotlight project; falls back automatically |
| SHOW_CHARTS / SHOW_FINANCE / SHOW_SALES | Optional section visibility |
| OUTPUT_FOLDER / LOG_FOLDER | Local output and log directories |
| DAY_FIRST | Interpretation of ambiguous numeric text dates |
| DUE_SOON_DAYS | Forward window for due-soon classification |
| CAPACITY_LOAD_MULTIPLIER / LONG_RUNNING_DAYS | Reusable management thresholds |
| PROJECT_ALIASES / NAME_ALIASES | Optional stable mappings for genuinely different naming conventions |
| REGISTER_PROJECTS | Optional stable mapping for otherwise unidentified registers |
| PORT / MAX_UPLOAD_MB | Local server port and upload size limit |

No weekly statistics are stored in configuration or report templates. The example project name in spotlight configuration and organization defaults are explicitly configurable metadata. Example counts in tests and reconciliation notes are fixture assertions, not production inputs.

## Printing and portability

**Print / Save as PDF** expands task, register and invoice sections. It restores the previous open/closed state after printing. Screen charts use bundled Chart.js; print uses a compact bar table and status table to avoid browser canvas-sizing problems. Tables repeat their headings and avoid splitting ordinary rows. Long tables naturally continue across pages.

The report uses local fonts and makes no external requests. Spreadsheet text is autoescaped through Jinja2; chart data uses safe JSON serialization. Spreadsheet markup is displayed as text rather than executed. The app restricts uploads to `.xlsx`, checks the expanded workbook size and uses generated output directories rather than trusting uploaded paths. Source workbooks uploaded through the interface are removed from temporary storage after processing. HTML reports remain in `output/` until you delete them.

## Tests

Run `python -m unittest discover -s tests -v` for synthetic workbook and cleanup checks. Private workbook fixtures, financial reconciliation notes, and generated reports are excluded from this repository.

## Project structure

```text
app.py                         Local upload interface
generate_report.py             CLI entry point
config.py                      Organization metadata and reusable rules
requirements.txt               Three direct dependencies
Start_Report_Generator.cmd     Weekly Windows launcher
Setup_Windows.cmd              One-time Windows setup
report_generator/
  models.py                    Normalized dataclasses
  normalization.py             Status, name, currency and date utilities
  excel_parser.py              Independent sheet parsers
  analytics.py                 Aggregations, spotlight, finance and sales
  narratives.py                Deterministic prose
  risks.py                     Risks and management actions
  renderer.py                  Context, template rendering, atomic CLI output
  logging_setup.py             Rotating technical logs
templates/                     Upload and report templates
static/                        CSS, report JavaScript, bundled Chart.js and license
tests/                         Synthetic automated tests
input/                         Optional place to keep weekly source files
output/                        Generated reports
```

## Troubleshooting

| Message / symptom | Resolution |
| --- | --- |
| No usable project/task source | Restore recognizable task or summary headers; see the input contract above |
| Reporting period unavailable | Add an explicit Reporting Period label and date range to the workbook |
| Missing formula results | Recalculate and save in Excel/LibreOffice, then upload again |
| Unknown status | Correct the source typo, or add an intentional synonym once to STATUS_ALIASES |
| Register project not identified | Put the project name in its heading or Project column; alternatively configure REGISTER_PROJECTS |
| Finance reconciliation required | Confirm receipts, invoice line allocation and inconsistent subtotals in the source workbook |
| Upload form expired | Reload the upload page after restarting the application |
| Port already in use | Stop the existing instance or change PORT in config.py |
| Start script says setup is needed | Run Setup_Windows.cmd in the extracted folder; virtual environments are not portable |

## Third-party components

The source uses [openpyxl's workbook loader](https://openpyxl.readthedocs.io/en/stable/_modules/openpyxl/reader/excel.html), [Flask's upload and download APIs](https://flask.palletsprojects.com/en/stable/patterns/fileuploads/), and Jinja2 autoescaping. [Chart.js 4.5.1](https://github.com/chartjs/Chart.js/releases/tag/v4.5.1) is bundled under its MIT license in `static/vendor/Chart.js-LICENSE.md`; it is embedded into each generated report.


## Vercel hosting

Import this repository into Vercel using the Flask framework preset. No build command or output directory is needed. The hosted app accepts workbooks up to 4 MB, returns self-contained HTML directly to the browser, and deletes temporary workbook files after processing. Reports are not retained on the server; download before leaving the page. The local app continues to support 20 MB workbooks. Hosted reports larger than 4 MB require the local generator. Updates to the connected main branch redeploy automatically.

