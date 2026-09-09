@echo off
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m venv .venv
) else (
  python -m venv .venv
)
if errorlevel 1 (
  echo Install Python 3.10 or newer from python.org, then run setup again.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Installation failed. Check your internet connection and try again.
  pause
  exit /b 1
)
echo Setup complete. Double-click Start_Report_Generator.cmd each week.
pause
