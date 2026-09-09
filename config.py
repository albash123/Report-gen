"""Organization settings and reusable rules. Never put weekly statistics here."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COMPANY_NAME = "Nexus Technologies"
REPORT_FILE_PREFIX = "Nexus"
DEFAULT_PREPARED_BY = "Albash ul Haq"
DEFAULT_ROLE = "Technical Project Manager"
SPOTLIGHT_PROJECT = "Hilal Publications"
SHOW_CHARTS = True
SHOW_FINANCE = True
SHOW_SALES = True
OUTPUT_FOLDER = BASE_DIR / "output"
LOG_FOLDER = BASE_DIR / "logs"
DAY_FIRST = True  # Text dates such as 05/10/2026 mean 5 October. Excel dates retain their value.
DUE_SOON_DAYS = 30
CAPACITY_LOAD_MULTIPLIER = 1.75
LONG_RUNNING_DAYS = 21
MAX_UPLOAD_MB = 20
MAX_EXPANDED_WORKBOOK_MB = 100
MAX_WORKSHEET_CELLS = 2_000_000
PORT = 5000

# Optional stable naming aliases, only if your source uses genuinely different names.
# Case, whitespace, punctuation and '&' versus 'and' are already normalized.
PROJECT_ALIASES = {}
NAME_ALIASES = {}
# Only needed for registers with no project column or identifiable project heading.
# Example: {"Task Register": "Your project name"}
REGISTER_PROJECTS = {}
