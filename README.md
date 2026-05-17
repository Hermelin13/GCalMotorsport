## GCalMotorsport — Race calendar manager & uploader

This repository scrapes race calendars (F1, Formula E, WEC) and prepares or uploads events to Google Calendar using a service account.
### Main files
- `f1_calendar.py` — scrapes the F1 calendar and creates time-specific events (qualifying/sprint/race).
- `fe_calendar.py` — scrapes Formula E and prefers precise RACE times (falls back to all-day events).
- `wec_calendar.py` — scrapes WEC and produces all-day events.
- `run_calendars.py` — launcher to run the individual scripts programmatically.
- `start_calendars.bat` / `start_calendars.ps1` — Windows helpers; the batch delegates argument parsing to the PowerShell wrapper.

### TODO
- Fix times for F1 and FE: ensure the scraper uses the `sessions['race']` times, preserves timezone offsets, and regenerates/upload events so calendar entries show correct local times.
- Fix WEC event naming: prefer `og:title`/`<h1>` or page title over short date-only anchors when constructing event summaries.

### Requirements
- Python 3.10+ (or compatible)
- Install dependencies:

```powershell
pip install -r requirements.txt
```

### Google service account setup
1. In Google Cloud Console create a Service Account and download the JSON key. Save it in the repo as `calendarcred.json` (or pass a different path with `--creds`).
2. From the JSON file note the `client_email` value.
3. In Google Calendar open the target calendar → Settings → Share with specific people → add the `client_email` and give it **Make changes to events** (Editor) permission.
### Usage examples

- Dry-run for Formula E (no writes):

```powershell
.\start_calendars.bat --which fe --dry-run
```

- Upload one series (use the provided `--calendar-id` and `calendarcred.json`):

```powershell
.\start_calendars.bat --which f1 --upload --calendar-id your_f1_id --creds calendarcred.json
```

- Upload all series using the IDs configured in `start_calendars.ps1`:

```powershell
.\start_calendars.bat --which all
```

### How it works
`start_calendars.ps1` parses the `--which` argument (`all`, `f1`, `fe`, `wec`), injects `--upload` when `--dry-run` is not present, inserts a default `--calendar-id` per series (if none was passed), and adds `--creds` if not supplied. It then calls `run_calendars.py` for each selected series.

### Troubleshooting tips
- If you get a 404 from the Calendar API, verify you used the exact *Calendar ID* (Google Calendar → Settings → Integrate → Calendar ID) and that the calendar is shared with the `client_email` from `calendarcred.json`.
- Always run `--dry-run` first to inspect the payload before uploading.
- If PowerShell blocks `.ps1` execution, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_calendars.ps1 --which f1 --dry-run
```

If you want me to prefill your calendar IDs into `start_calendars.ps1`, send the IDs for F1 / FE / WEC and I will update the script.

### Notes
- This tool is intended for personal use. Before large automated uploads, check Google Calendar API quotas and the deduplication logic.
## GCalMotorsport — správce a uploader závodních kalendářů
Krátce: tento repozitář sbírá závodní kalendáře (F1, FE, WEC) a připraví nebo nahraje události do Google Calendar pomocí service accountu.
### Hlavní soubory
- `f1_calendar.py` — stáhne F1 kalendář a vytvoří časově přesné události (kvalifikace/sprint/race).
- `fe_calendar.py` — stáhne Formula E a preferuje přesné časy RACE (fallback: all-day).
- `wec_calendar.py` — stáhne WEC a vytváří all-day události.
- `run_calendars.py` — univerzální launcher pro spuštění jednotlivých skriptů.
- `start_calendars.bat` / `start_calendars.ps1` — helpery pro Windows (delegují na PowerShell wrapper).
### Požadavky
- Python 3.10+ (nebo kompatibilní)
- Nainstalované závislosti:

```powershell
pip install -r requirements.txt
```
### Nastavení Google service account
1. V Google Cloud Console vytvořte Service Account a vygenerujte JSON klíč. Uložte jej do repa jako `calendarcred.json` nebo jinam a použijte `--creds`.
2. V JSON najděte `client_email` (např. `botadam@rowcalendar.iam.gserviceaccount.com`).
3. V Google Calendar otevřete cílový kalendář → Settings → Share with specific people → přidejte `client_email` a dejte roli **Make changes to events** (Editor).
### Použití — příklady

- Dry‑run pro Formula E (nezapisuje nic):

```powershell
.\start_calendars.bat --which fe --dry-run
```
- Upload pro jednu sérii (použije předané `--calendar-id` a `calendarcred.json`):

```powershell
.\start_calendars.bat --which f1 --upload --calendar-id your_f1_id --creds calendarcred.json
```
- Upload pro všechny série (pokud máte přednastavené ID v `start_calendars.ps1`):

```powershell
.\start_calendars.bat --which all
```
### Jak to funguje
- `start_calendars.ps1` zpracuje `--which` (all/f1/fe/wec), doplní `--upload` pokud není `--dry-run`, doplní `--calendar-id` pro danou sérii podle nastavení v souboru a `--creds` pokud není uvedeno. Poté spouští `run_calendars.py` pro každou vybranou sérii.
### Tipy a troubleshooting
- Pokud API vrací 404, zkontrolujte, že jste použili přesné *Calendar ID* (Settings → Integrate → Calendar ID) a že kalendář sdílíte se `client_email` z `calendarcred.json`.
- Nejdříve vždy spusťte `--dry-run`, abyste viděli, co se bude nahrávat.
- Pokud PowerShell nepovolí spouštění `.ps1`, použijte:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_calendars.ps1 --which f1 --dry-run
```
Chcete‑li, abych automaticky vložil vaše calendar‑ID do `start_calendars.ps1`, pošlete mi ID (F1 / FE / WEC) a já to upravím.
### Licence / poznámky
- Tento nástroj slouží pro osobní použití; před masovými uploady doporučuji zkontrolovat limity Google Calendar API a logiku deduplikace.
# GCalMotorsport — Formula E calendar uploader

This repository contains `fe_calendar.py` which scrapes the Formula E calendar and can upload events to Google Calendar using a service account.

Quick setup

- Install dependencies:

```bash
pip install -r requirements.txt
```

- Create a Google Cloud service account and download the JSON key file. Grant it access to the calendar you want to update by sharing the calendar with the service account email (found in the JSON under `client_email`).

- Save the JSON key as `calendarcred.json` (or point `--creds` to the file).

Usage

- Dry-run (prepare Google Calendar payload for 2025-26 and print it):

```bash
python fe_calendar.py 2025-26 --dry-run
```

- Upload to a calendar (will prompt for confirmation):

```bash
python fe_calendar.py 2025-26 --upload --calendar-id YOUR_CALENDAR_ID --creds calendarcred.json
```

- Windows helper (edit `upload_fe.bat` to set `CALENDAR_ID` and `CREDS`):

```
upload_fe.bat
```

Notes

- The script prefers precise `RACE` session times when available; otherwise it creates all-day events.
- Use `--include-other` to skip season filtering.
- The `--dry-run` prints the Google Calendar event payloads without performing any API calls.
**GCalMotorsport**

- **Purpose:** Extract race start times for Formula 1, Formula E and WEC and insert them into a Google Calendar using a service account.
- **Location:** `gcalmotorsport.py`

**Quick Start**
- **Install dependencies:**

```bash
pip install -r requirements.txt
playwright install chromium
```

- **Run (example for year 2026):**

```bash
python gcalmotorsport.py --series all --year 2026 --season 2025-26 --creds calendarcred.json --calendar primary
```

- **Run once-per-year (script will record processed year):**

```bash
python gcalmotorsport.py --series all --year 2026 --season 2025-26 --creds calendarcred.json --calendar primary --once-per-year
```

**Options (high level)**
- **`--series`**: `f1`, `fe`, `wec`, `all` (which series to process).
- **`--year`**: Year to select events for (F1/WEC use numeric year; FE uses `--season` but events are filtered to `--year`).
- **`--season`**: Formula E season string (e.g. `2025-26`).
- **`--creds`**: Path to Google service account JSON.
- **`--calendar`**: Target Google Calendar ID (default `primary`).
- **`--once-per-year`**: Record that a series/year was processed and skip it on subsequent runs (state saved to `gcalmotorsport_state.json` by default).
- **`--state-file`**: Custom state file path.

**How the year/season logic works**
- `--year` controls which events are inserted (all events whose start date has that year). This allows you to pass a FE season like `2025-26` with `--season` while still selecting events for `--year 2026` (or `2025`).

**Credentials & Permissions**
- Use a Google service account JSON. Place it next to the script and point `--creds` to it (e.g. `calendarcred.json`).
- Share the target Google Calendar with the service account email (grant "Make changes to events").
- Security: keep the JSON private. If the key leaks, rotate/delete it in Google Cloud Console.

**Notes & Caveats**
- Formula E scraping uses Playwright (headless Chromium) because the official site is JS-rendered. If FE page structure changes, the scraping code may need updates.
- WEC extraction downloads the event `.ics` and parses the race VEVENT; if the WEC site changes links or structure, this may need tweaking.
- The script filters events to `--year`; you can run for any year (e.g. `2027`) after official times are published.

**Scheduling suggestions**
- Run daily/weekly via Task Scheduler or cron; use `--once-per-year` so insertion occurs only once after times are published.

Windows Task Scheduler — minimal example (powershell):

```powershell
# Run daily at 03:00
schtasks /Create /SC DAILY /TN "GCalMotorsport" /TR "C:\Python39\python.exe C:\path\to\GCalMotorsport\gcalmotorsport.py --series all --year 2026 --season 2025-26 --creds C:\path\to\calendarcred.json --calendar primary --once-per-year" /ST 03:00
```

**Troubleshooting**
- If no events appear: verify the service account has calendar access and that the source sites (Jolpica, fiaformulae, fiawec) have session times published.
- To re-run a series-year after `--once-per-year`, delete or edit `gcalmotorsport_state.json`.

**Contributing / Extending**
- Add selectors or fallback URLs if one data source changes.
- Add per-event tracking (instead of per-year) if you want finer control.

---
Generated by your local helper script. For help, open an issue or ask directly in the repo.
