@echo off
REM ─── GCalMotorsport – insert F1 / FE / WEC races into Google Calendar ───
REM
REM Before first run:
REM   pip install -r requirements.txt
REM   playwright install chromium
REM
REM Edit the variables below to match your setup.

set CREDS=motorsport-calendar.json
set CALENDAR=primary
set YEAR=2026
set SEASON=2025-26

python gcalmotorsport.py ^
    --series all ^
    --year %YEAR% ^
    --season %SEASON% ^
    --creds %CREDS% ^
    --calendar %CALENDAR%

pause
