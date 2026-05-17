@echo off
REM start_calendars.bat
REM Usage:
REM   start_calendars.bat --F1       -> upload F1 only to F1 calendar
REM   start_calendars.bat --FE       -> upload FE only to FE calendar
REM   start_calendars.bat --WEC      -> upload WEC only to WEC calendar
REM   start_calendars.bat             -> upload all three (F1, FE, WEC)

REM === Configure calendar IDs below ===
set F1_CAL=F1_CAL_ID_HERE
set FE_CAL=FE_CAL_ID_HERE
set WEC_CAL=WEC_CAL_ID_HERE
set CREDS=calendarcred.json

REM Delegate all argument parsing to PowerShell wrapper for reliability
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_calendars.ps1" %*