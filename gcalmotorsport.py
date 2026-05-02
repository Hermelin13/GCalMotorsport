#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gcalmotorsport.py

Extract race start times for Formula 1, Formula E, and WEC,
then insert them into Google Calendar.

Data sources:
  F1  – Jolpica (Ergast successor) JSON API
  FE  – fiaformulae.com  (Playwright required for JS rendering)
  WEC – fiawec.com  (iCal files downloaded per race)

Usage:
  python gcalmotorsport.py --series all  --year 2026 --season 2025-26 \\
      --creds service_account.json --calendar primary

  python gcalmotorsport.py --series f1   --year 2026 --creds creds.json
  python gcalmotorsport.py --series fe   --season 2025-26 --creds creds.json
  python gcalmotorsport.py --series wec  --year 2026 --creds creds.json
"""

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── Google Calendar colour IDs ──────────────────────────────────────────────
COLOR_F1  = "11"   # Tomato  – red
COLOR_FE  = "5"    # Banana  – yellow
COLOR_WEC = "10"   # Sage    – green

# ── Shared HTTP session ──────────────────────────────────────────────────────
def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  FORMULA 1 – Jolpica API                                                 ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def fetch_f1_races(year: int) -> list[dict]:
    """Fetch F1 race schedule from the Jolpica (Ergast successor) API."""
    print(f"\n[F1] Fetching {year} schedule from Jolpica API …")
    url = f"https://api.jolpica.com/ergast/f1/{year}/races.json?limit=30"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    races = resp.json()["MRData"]["RaceTable"]["Races"]

    events: list[dict] = []
    for r in races:
        date_s = r["date"]          # "2026-03-22"
        time_s = r.get("time", "")  # "13:00:00Z" or absent

        if time_s:
            start = datetime.strptime(
                f"{date_s}T{time_s}", "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc)
            end = start + timedelta(hours=2)
        else:
            start = end = None  # will become an all-day event

        circuit = r["Circuit"]
        location = (
            f"{circuit['Location']['locality']}, "
            f"{circuit['Location']['country']}"
        )
        events.append({
            "summary":    f"F1: {r['raceName']}",
            "location":   location,
            "description": f"Round {r['round']} · {circuit['circuitName']}",
            "start":      start,
            "end":        end,
            "start_date": date_s,
            "color":      COLOR_F1,
        })

    print(f"[F1] Found {len(events)} races.")
    return events


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  WEC – iCal download per race                                            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

_WEC_BASE = "https://www.fiawec.com"

def fetch_wec_races(year: int) -> list[dict]:
    """
    Fetch WEC race schedule from fiawec.com.

    1. Scrape the homepage navigation for race page URLs.
    2. For each race page, find the "ADD TO MY CALENDAR" iCal link ID.
    3. Download the .ics file and extract the Race-session DTSTART.
    """
    print(f"\n[WEC] Fetching {year} schedule from fiawec.com …")
    sess = _session()

    # ── 1. Collect race page URLs ────────────────────────────────────────────
    resp = sess.get(f"{_WEC_BASE}/en", timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    race_urls: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        # Must be a race event page and contain the target year
        if (
            f"-{year}" in href
            and "/race/" in href
            and "prologue" not in href.lower()
            and "test"     not in href.lower()
            and "/calendar/" not in href
            and "/document/" not in href
            and "/summary/"  not in href
        ):
            full = f"{_WEC_BASE}{href}" if href.startswith("/") else href
            if full not in seen:
                seen.add(full)
                race_urls.append(full)

    print(f"[WEC] Found {len(race_urls)} race page(s).")
    if not race_urls:
        print("[WEC] No race URLs found – the site navigation may have changed.")

    events: list[dict] = []
    for race_url in race_urls:
        slug = race_url.rstrip("/").split("/")[-1]
        print(f"[WEC]   → {slug} …")

        # ── 2. Find the iCal ID ──────────────────────────────────────────────
        try:
            page_resp = sess.get(race_url, timeout=30)
            page_resp.raise_for_status()
        except Exception as exc:
            print(f"[WEC]   ✗ Could not fetch race page: {exc}")
            continue

        page_soup = BeautifulSoup(page_resp.text, "html.parser")
        ical_id: str | None = None
        for a in page_soup.find_all("a", href=True):
            m = re.search(r"/race/calendar/(\d+)", a["href"])
            if m:
                ical_id = m.group(1)
                break

        if not ical_id:
            print(f"[WEC]   ✗ No iCal link found; skipping.")
            continue

        # ── 3. Download & parse iCal ─────────────────────────────────────────
        try:
            ical_resp = sess.get(
                f"{_WEC_BASE}/en/race/calendar/{ical_id}", timeout=30
            )
            ical_resp.raise_for_status()
        except Exception as exc:
            print(f"[WEC]   ✗ Could not download iCal ({ical_id}): {exc}")
            continue

        race_start, race_end, race_name = _parse_wec_ical(ical_resp.content)
        if race_start is None:
            print(f"[WEC]   ✗ No Race event found in iCal; skipping.")
            continue

        display_name = (
            race_name
            or slug.replace(f"-{year}", "").replace("-", " ").title()
        )
        events.append({
            "summary":     f"WEC: {display_name}",
            "location":    "",
            "description": f"FIA WEC {year}",
            "start":       race_start,
            "end":         race_end or (race_start + timedelta(hours=6)),
            "start_date":  race_start.strftime("%Y-%m-%d"),
            "color":       COLOR_WEC,
        })
        print(
            f"[WEC]   ✓ {display_name} – "
            f"{race_start.strftime('%Y-%m-%d %H:%M UTC')}"
        )

    print(f"[WEC] Processed {len(events)} race(s).")
    return events


def _parse_wec_ical(
    data: bytes,
) -> tuple[datetime | None, datetime | None, str | None]:
    """Return (start_utc, end_utc, summary) for the Race event in a WEC .ics file."""
    try:
        from icalendar import Calendar  # type: ignore
    except ImportError:
        raise RuntimeError(
            "The 'icalendar' package is required for WEC. "
            "Run: pip install icalendar"
        )

    cal = Calendar.from_ical(data)
    for comp in cal.walk():
        if comp.name != "VEVENT":
            continue
        summary = str(comp.get("SUMMARY", ""))
        # Race event: contains 'race' or 'hours', but NOT practice/qualifying
        if re.search(r"\b(race|hours)\b", summary, re.IGNORECASE) and not re.search(
            r"\b(practice|qualifying|warm.?up|hyperpole)\b", summary, re.IGNORECASE
        ):
            dtstart = comp.get("DTSTART")
            dtend   = comp.get("DTEND")
            if dtstart is None:
                continue
            start = dtstart.dt
            end   = dtend.dt if dtend else None

            # Ensure both are timezone-aware datetimes in UTC
            if isinstance(start, date) and not isinstance(start, datetime):
                start = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
            elif isinstance(start, datetime) and start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            else:
                start = start.astimezone(timezone.utc)

            if end is not None:
                if isinstance(end, date) and not isinstance(end, datetime):
                    end = datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)
                elif isinstance(end, datetime) and end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                else:
                    end = end.astimezone(timezone.utc)

            return start, end, summary

    return None, None, None


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  FORMULA E – Playwright (JS-rendered site)                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

_FE_BASE     = "https://www.fiaformulae.com"
_FE_MONTHS   = {
    m: i + 1
    for i, m in enumerate(
        "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
    )
}

def fetch_fe_races(season: str) -> list[dict]:
    """
    Fetch Formula E race schedule using Playwright.

    The FIA Formula E website is a JS-heavy React app; the schedule
    is not available in the raw HTML.  We launch a headless Chromium
    with its timezone set to UTC so all displayed times are in UTC.

    Steps:
      1. Load the calendar overview page and collect race page URLs.
      2. For each race page, extract the "RDN DD MMM YYYY" round date
         and find the matching Race-session time.
      3. Convert to UTC datetime (already UTC due to browser timezone).
    """
    print(f"\n[FE] Fetching {season} schedule with Playwright …")
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        raise RuntimeError(
            "Playwright is required for Formula E.\n"
            "Install with:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    events: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        # UTC timezone → displayed times will be UTC
        ctx = browser.new_context(
            timezone_id="UTC",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()

        # ── 1. Calendar overview → race URLs ────────────────────────────────
        cal_url = f"{_FE_BASE}/en/championship/race-calendar"
        try:
            page.goto(cal_url, wait_until="networkidle", timeout=90_000)
        except Exception as exc:
            print(f"[FE] ✗ Could not load calendar page: {exc}")
            ctx.close(); browser.close()
            return []

        soup = BeautifulSoup(page.content(), "html.parser")
        race_links: list[str] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href: str = a["href"]
            if f"/calendar/{season}/r" in href:
                full = (
                    f"{_FE_BASE}{href}" if href.startswith("/") else href
                )
                if full not in seen:
                    seen.add(full)
                    race_links.append(full)

        print(f"[FE] Found {len(race_links)} race link(s) on calendar page.")

        # ── 2. Visit each race page ──────────────────────────────────────────
        for race_url in race_links:
            slug = race_url.rstrip("/").split("/")[-1]   # e.g. "r9-monaco"
            print(f"[FE]   → {slug} …")

            try:
                page.goto(race_url, wait_until="networkidle", timeout=90_000)
            except Exception as exc:
                print(f"[FE]   ✗ Load failed: {exc}")
                continue

            # innerText gives the visible text (not raw HTML tags)
            full_text: str = page.evaluate("document.body.innerText") or ""

            # ── Determine the race date from "RDN DD MMM YYYY" ──────────────
            rd_match = re.search(
                r"RD\d+\s+(\d{1,2})\s+([A-Z]{3,})\s+(\d{4})",
                full_text,
            )
            if rd_match:
                day = int(rd_match.group(1))
                mon = _FE_MONTHS.get(rd_match.group(2)[:3].upper(), 0)
                yr  = int(rd_match.group(3))
                date_prefix = f"{day:02d}/{mon:02d}" if mon else ""
            else:
                date_prefix = ""
                yr = int("20" + season.split("-")[1])

            # ── Find Race-session start time in UTC ──────────────────────────
            # Page schedule format (UTC browser): "DD/MM HH:MM - HH:MMRace"
            # We try two patterns: date-anchored first, then generic last Race.
            race_dt: datetime | None = None

            if date_prefix:
                # Pattern: "16/05 13:05 - 14:00Race" (UTC due to browser tz)
                m = re.search(
                    rf"{re.escape(date_prefix)}\s+(\d{{2}}:\d{{2}})"
                    r"\s*-\s*\d{2}:\d{2}\s*Race",
                    full_text,
                    re.IGNORECASE,
                )
                if m:
                    try:
                        race_dt = datetime.strptime(
                            f"{date_prefix}/{yr} {m.group(1)}",
                            "%d/%m/%Y %H:%M",
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass

            if race_dt is None:
                # Fallback: any "DD/MM HH:MM - HH:MM Race" line
                for m in re.finditer(
                    r"(\d{2}/\d{2})\s+(\d{2}:\d{2})\s*-\s*\d{2}:\d{2}\s*Race",
                    full_text,
                    re.IGNORECASE,
                ):
                    d_s, t_s = m.group(1), m.group(2)
                    try:
                        race_dt = datetime.strptime(
                            f"{d_s}/{yr} {t_s}", "%d/%m/%Y %H:%M"
                        ).replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue

            if race_dt is None:
                print(f"[FE]   ✗ Race time not found; skipping.")
                continue

            # ── Extract event name ───────────────────────────────────────────
            raw_title = page.title() or ""
            name = re.sub(
                r"(?i)\babb\b|\bfia\b|\bformula\s*e\b|\bhankook\b",
                "",
                raw_title,
            )
            name = re.sub(r"[\s|·\-:]{2,}", " ", name).strip(" |·-:")
            if len(name) < 3:
                name = slug.replace("-", " ").title()

            events.append({
                "summary":     f"FE: {name}",
                "location":    "",
                "description": f"Formula E Season {season}",
                "start":       race_dt,
                "end":         race_dt + timedelta(minutes=55),
                "start_date":  race_dt.strftime("%Y-%m-%d"),
                "color":       COLOR_FE,
            })
            print(
                f"[FE]   ✓ {name} – "
                f"{race_dt.strftime('%Y-%m-%d %H:%M UTC')}"
            )

        ctx.close()
        browser.close()

    print(f"[FE] Found {len(events)} race(s).")
    return events


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  Google Calendar insertion                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def _gcal_service(creds_path: str):
    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return build("calendar", "v3", credentials=creds)


def insert_events(service, calendar_id: str, events: list[dict]) -> dict:
    """
    Insert events into Google Calendar.
    Skips events whose summary already exists in the same time window.
    """
    inserted: list[dict] = []
    skipped:  list[str]  = []
    errors:   list[dict] = []

    for ev in events:
        start_dt: datetime | None = ev.get("start")

        if start_dt is not None:
            start_s = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_s   = ev["end"].strftime("%Y-%m-%dT%H:%M:%SZ")
            start_body = {"dateTime": start_s, "timeZone": "UTC"}
            end_body   = {"dateTime": end_s,   "timeZone": "UTC"}
            # Deduplication window: ±1 h around the start time
            time_min = (start_dt - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            time_max = (start_dt + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            # All-day fallback (F1 race without confirmed time)
            date_s = ev["start_date"]
            start_body = {"date": date_s}
            end_body   = {
                "date": (
                    datetime.strptime(date_s, "%Y-%m-%d") + timedelta(days=1)
                ).strftime("%Y-%m-%d")
            }
            time_min = f"{date_s}T00:00:00Z"
            time_max = f"{date_s}T23:59:59Z"

        # Check for duplicate
        try:
            existing = service.events().list(
                calendarId=calendar_id,
                q=ev["summary"],
                singleEvents=True,
                orderBy="startTime",
                timeMin=time_min,
                timeMax=time_max,
            ).execute()
            if any(
                item.get("summary") == ev["summary"]
                for item in existing.get("items", [])
            ):
                skipped.append(ev["summary"])
                continue
        except Exception:
            pass  # if duplicate check fails, still attempt insertion

        body = {
            "summary":     ev["summary"],
            "location":    ev.get("location", ""),
            "description": ev.get("description", ""),
            "start":       start_body,
            "end":         end_body,
            "colorId":     ev.get("color", "8"),
            "reminders":   {"useDefault": False, "overrides": []},
        }

        try:
            created = service.events().insert(
                calendarId=calendar_id,
                body=body,
                sendUpdates="none",
            ).execute()
            inserted.append({"summary": created["summary"], "id": created["id"]})
        except Exception as exc:
            errors.append({"summary": ev["summary"], "error": str(exc)})

    return {"inserted": inserted, "skipped": skipped, "errors": errors}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CLI entry point                                                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Extract F1 / Formula E / WEC race start times "
            "and insert them into Google Calendar."
        )
    )
    ap.add_argument(
        "--series",
        choices=["f1", "fe", "wec", "all"],
        default="all",
        help="Which series to process (default: all)",
    )
    ap.add_argument(
        "--year",
        type=int,
        default=2026,
        help="Season year for F1 and WEC (default: 2026)",
    )
    ap.add_argument(
        "--season",
        default="2025-26",
        help="Formula E season string, e.g. 2025-26 (default: 2025-26)",
    )
    ap.add_argument(
        "--calendar",
        default="primary",
        help="Target Google Calendar ID (default: primary)",
    )
    ap.add_argument(
        "--creds",
        required=True,
        help="Path to Google service-account JSON credentials file",
    )
    args = ap.parse_args()

    all_events: list[dict] = []

    if args.series in ("f1", "all"):
        all_events.extend(fetch_f1_races(args.year))

    if args.series in ("fe", "all"):
        all_events.extend(fetch_fe_races(args.season))

    if args.series in ("wec", "all"):
        all_events.extend(fetch_wec_races(args.year))

    if not all_events:
        print("\nNo events to insert.")
        return

    print(f"\nTotal events to process: {len(all_events)}")
    print("Connecting to Google Calendar API …")

    svc = _gcal_service(args.creds)
    result = insert_events(svc, args.calendar, all_events)

    print("\n══ Summary ══════════════════════════")
    print(f"  Inserted : {len(result['inserted'])}")
    print(f"  Skipped  : {len(result['skipped'])}  (already exist)")
    print(f"  Errors   : {len(result['errors'])}")
    for err in result["errors"]:
        print(f"  ✗ {err['summary']}: {err['error']}")


if __name__ == "__main__":
    main()
