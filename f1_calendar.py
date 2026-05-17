#!/usr/bin/env python3
"""Fetch full F1 race calendar from formula1.com and print JSON list of events."""
import sys
import json
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests
import argparse

# Google API
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except Exception:
    service_account = None
    build = None
from bs4 import BeautifulSoup

BASE = "https://www.formula1.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_f1_calendar(year: int) -> list[dict]:
    url = f"{BASE}/en/racing/{year}"
    sess = requests.Session()
    sess.headers.update(HEADERS)

    resp = sess.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Collect candidate race links that contain the year
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if f"/en/racing/{year}/" in href:
            full = href if href.startswith("http") else BASE + href
            if full not in seen:
                seen.add(full)
                links.append(full)

    events = []
    # Try to canonicalize and visit each candidate link
    for link in links:
        try:
            r = sess.get(link, timeout=30)
            r.raise_for_status()
        except Exception:
            continue
        ps = BeautifulSoup(r.text, "html.parser")

        # Title
        title = (ps.find("h1") or ps.title or ps.find("meta", {"property": "og:title"}))
        if hasattr(title, "text"):
            title_text = title.text.strip()
        elif title and title.get("content"):
            title_text = title.get("content").strip()
        else:
            title_text = link.rstrip("/").split("/")[-1].replace("-", " ").title()

        # Date/time — prefer explicit schedule RACE time on the event page.
        dt = None
        page_text = ps.get_text(" ", strip=True)

        # Attempt several regex patterns to find the RACE session and its time.
        # Examples on the site: "19 Jul RACE 15:00" or collapsed "19JulRACE15:00".
        patterns = [
            r"(\d{1,2})\s*([A-Za-z]{3,})\s*RACE\s*[:\s]*(\d{1,2}:\d{2})",
            r"(\d{1,2})([A-Za-z]{3})\s*RACE\s*(\d{1,2}:\d{2})",
            r"RACE\s*(\d{1,2}:\d{2})",
        ]

        match = None
        for pat in patterns:
            m = re.search(pat, page_text, re.IGNORECASE)
            if m:
                match = m
                break

        if match:
            try:
                if match.lastindex == 3:
                    day = int(match.group(1))
                    mon_s = match.group(2)
                    time_s = match.group(3)
                elif match.lastindex == 1:
                    # pattern matched only time (fallback)
                    day = None
                    mon_s = None
                    time_s = match.group(1)
                else:
                    day = None; mon_s = None; time_s = None

                # Resolve month
                month = None
                if mon_s:
                    mon = mon_s[:3].title()
                    months = {m[:3]: i for i, m in enumerate(
                        ["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}
                    month = months.get(mon[:3].title(), None) or months.get(mon.upper(), None)

                # Determine timezone from URL slug heuristic
                slug = link.rstrip('/').split('/')[-1].lower()
                tz_map = {
                    'belgium': 'Europe/Brussels',
                    'great-britain': 'Europe/London',
                    'britain': 'Europe/London',
                    'monaco': 'Europe/Monaco',
                    'italy': 'Europe/Rome',
                    'canada': 'America/Toronto',
                    'bahrain': 'Asia/Bahrain',
                    'japan': 'Asia/Tokyo',
                    'australia': 'Australia/Sydney',
                    'usa': 'America/Chicago',
                }
                tzname = tz_map.get(slug, None)

                if day and month and time_s and tzname:
                    hh, mm = map(int, time_s.split(':'))
                    dt_local = datetime(year, month, day, hh, mm, tzinfo=ZoneInfo(tzname))
                    dt = dt_local.astimezone(timezone.utc)
                elif day and month and time_s:
                    # no tz info — assume UTC for safety
                    hh, mm = map(int, time_s.split(':'))
                    dt = datetime(year, month, day, hh, mm, tzinfo=timezone.utc)
            except Exception:
                dt = None
        else:
            # Fallback: try <time datetime="..."> or generic date mentions
            ttag = ps.find("time")
            if ttag and ttag.get("datetime"):
                try:
                    dt = datetime.fromisoformat(ttag.get("datetime"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    dt = None
            if dt is None:
                m = re.search(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})(?:\s+at\s+(\d{1,2}:\d{2}))?", page_text)
                if m:
                    date_str = m.group(1)
                    time_str = m.group(2) or "00:00"
                    try:
                        dt = datetime.strptime(f"{date_str} {time_str}", "%d %B %Y %H:%M").replace(tzinfo=timezone.utc)
                    except Exception:
                        try:
                            dt = datetime.strptime(f"{date_str} {time_str}", "%d %b %Y %H:%M").replace(tzinfo=timezone.utc)
                        except Exception:
                            dt = None

        # Location / circuit — try meta description or specific labels
        location = ""
        meta_desc = ps.find("meta", {"name": "description"}) or ps.find("meta", {"property": "og:description"})
        if meta_desc and meta_desc.get("content"):
            location = meta_desc.get("content").strip()
        # Try to find a circuit/locality element
        if not location:
            for cls in ("c-location", "circuit", "raceLocation", "location"):
                el = ps.find(class_=cls)
                if el:
                    location = el.get_text(" ", strip=True)
                    break

        # Extract session times (only save qualifying, sprint, race)
        sessions = {
            "qualifying": None,
            "sprint": None,
            "race": None,
        }

        # Find session occurrences with optional day+mon and a time
        session_pat = re.compile(
            r"(?:(\d{1,2})\s*([A-Za-z]{3}))?\s*(PRACTICE\s*1|PRACTICE\s*2|PRACTICE\s*3|QUALIFYING|SPRINT|RACE)\s*[:\s-]*?(\d{1,2}:\d{2})",
            re.IGNORECASE,
        )

        for m in session_pat.finditer(page_text):
            day_g, mon_g, sess_name, time_s = m.group(1), m.group(2), m.group(3), m.group(4)
            sess_key = sess_name.lower().replace(" ", "")
            # map session key variants
            # Skip practice sessions per user request
            if sess_key.startswith("practice"):
                continue
            elif sess_key.startswith("qual"):
                key = "qualifying"
            elif sess_key.startswith("sprint"):
                key = "sprint"
            elif sess_key.startswith("race"):
                key = "race"
            else:
                continue

            # resolve date/time
            try:
                if day_g and mon_g:
                    day_i = int(day_g)
                    mon = mon_g[:3].title()
                    months = {m[:3]: i for i, m in enumerate(
                        ["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}
                    month_i = months.get(mon[:3].title(), None) or months.get(mon.upper(), None)
                    slug = link.rstrip('/').split('/')[-1].lower()
                    tz_map = {
                        'belgium': 'Europe/Brussels',
                        'great-britain': 'Europe/London',
                        'britain': 'Europe/London',
                        'monaco': 'Europe/Monaco',
                        'italy': 'Europe/Rome',
                        'canada': 'America/Toronto',
                        'bahrain': 'Asia/Bahrain',
                        'japan': 'Asia/Tokyo',
                        'australia': 'Australia/Sydney',
                        'usa': 'America/Chicago',
                    }
                    tzname = tz_map.get(slug, None)
                    hh, mm = map(int, time_s.split(':'))
                    if month_i and tzname:
                        dt_local = datetime(year, month_i, day_i, hh, mm, tzinfo=ZoneInfo(tzname))
                        sessions[key] = dt_local.astimezone(timezone.utc).isoformat()
                    elif month_i:
                        sessions[key] = datetime(year, month_i, day_i, hh, mm, tzinfo=timezone.utc).isoformat()
                else:
                    # no date found — try to use previously parsed dt as reference or leave None
                    if dt is not None:
                        hh, mm = map(int, time_s.split(':'))
                        sessions[key] = datetime(dt.year, dt.month, dt.day, hh, mm, tzinfo=timezone.utc).isoformat()
            except Exception:
                pass

        events.append({
            "summary": title_text,
            "start": dt.isoformat() if dt else None,
            "sessions": sessions,
        })

    # Deduplicate by summary
    seen_summ = set()
    unique = []
    for ev in events:
        key = ev.get("summary") or ev.get("url")
        if key in seen_summ:
            continue
        seen_summ.add(key)
        unique.append(ev)

    return unique


def sessions_to_gcal_events(events: list[dict], color_id: str = "10") -> list[dict]:
    """Convert parsed events with `sessions` into Google Calendar event payloads.

    For each session present (qualifying, sprint, race) create an event with a
    reasonable default duration (qualifying=1h, sprint=1h, race=2h). Times are
    expected to be ISO strings with timezone info (UTC); otherwise they're
    treated as UTC.
    """
    gcal_events = []
    defaults = {"qualifying": timedelta(hours=1), "sprint": timedelta(hours=1), "race": timedelta(hours=2)}

    for ev in events:
        summary_base = ev.get("summary") or "F1 Event"
        sessions = ev.get("sessions") or {}
        # description: include all available session times
        descr_lines = []
        for k in ("qualifying", "sprint", "race"):
            v = sessions.get(k)
            if v:
                descr_lines.append(f"{k.capitalize()}: {v}")

        description = "\n".join(descr_lines) if descr_lines else ""

        for k, iso in sessions.items():
            if not iso:
                continue
            if k not in defaults:
                continue
            try:
                dt = datetime.fromisoformat(iso)
            except Exception:
                # best-effort parse fallback
                try:
                    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                except Exception:
                    continue

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            end = dt + defaults[k]

            gcal_events.append({
                "summary": f"{summary_base} — {k.capitalize()}",
                "start": {"dateTime": dt.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
                "colorId": color_id,
                "description": description,
            })

    return gcal_events


def insert_events(service, calendar_id: str, events: list[dict], color_id: str = "10") -> dict:
    """Insert/update/delete events in Google Calendar similar to GCalVeslo behavior.

    For each event: search existing by `q=summary`. If an existing event with
    identical start and end exists, skip. Otherwise delete matching-summary
    events and insert the new one. Returns a summary dict.
    """
    inserted = []
    deleted = []
    skipped = []

    for ev in events:
        summary = ev.get("summary", "")
        start_dt = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date")
        end_dt = ev.get("end", {}).get("dateTime") or ev.get("end", {}).get("date")

        try:
            existing = service.events().list(
                calendarId=calendar_id,
                q=summary,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
        except Exception as e:
            print("Failed to list existing events:", e)
            existing = {"items": []}

        found_same_date = False
        # Delete events with same summary but different dates
        for item in existing.get("items", []):
            item_id = item.get("id")
            item_summary = item.get("summary", "").strip().lower()
            if item_summary != summary.strip().lower():
                continue

            item_start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
            item_end = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")

            if item_start == start_dt and item_end == end_dt:
                found_same_date = True
                break
            # delete outdated duplicate
            try:
                service.events().delete(calendarId=calendar_id, eventId=item_id).execute()
                deleted.append(item_id)
            except Exception as e:
                print(f"Failed to delete event {item_id}:", e)

        if found_same_date:
            skipped.append({"summary": summary, "date": start_dt})
            continue

        # Insert new event
        body = ev.copy()
        # Ensure no reminders are sent
        if isinstance(body.get("reminders"), dict):
            body["reminders"] = {"useDefault": False, "overrides": []}

        try:
            created = service.events().insert(calendarId=calendar_id, body=body, sendUpdates='none').execute()
            inserted.append({"summary": created.get("summary"), "id": created.get("id"), "date": start_dt})
        except Exception as e:
            print("Failed to insert event:", e)

    return {"inserted": inserted, "deleted": deleted, "skipped": skipped}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch F1 calendar and optionally upload to Google Calendar")
    parser.add_argument("year", nargs="?", default=2026, type=int)
    parser.add_argument("--upload", action="store_true", help="Upload generated events to Google Calendar")
    parser.add_argument("--calendar-id", default="family16658134994112439829@group.calendar.google.com", help="Target Google Calendar ID (email or calendar ID)")
    parser.add_argument("--creds", default="calendarcred.json", help="Path to service account JSON credentials")
    args = parser.parse_args()

    year = args.year
    evs = fetch_f1_calendar(year)

    if not args.upload:
        print(json.dumps(evs, indent=2, ensure_ascii=False))
        sys.exit(0)

    # prepare gcal payloads
    gcal_events = sessions_to_gcal_events(evs)

    # calendar id and creds default to values used in GCalVeslo
    calid = args.calendar_id

    if service_account is None or build is None:
        print("ERROR: google-auth or google-api-python-client not installed.")
        sys.exit(3)

    # Create credentials and service
    creds = service_account.Credentials.from_service_account_file(args.creds, scopes=["https://www.googleapis.com/auth/calendar"])
    service = build("calendar", "v3", credentials=creds)

    # Proceed to upload without interactive confirmation
    print(f"Uploading {len(gcal_events)} events to calendar: {calid}")

    # Insert/update/delete events using GCalVeslo-style logic
    result = insert_events(service, calid, gcal_events)
    print("Upload summary:")
    print(f"  Inserted: {len(result.get('inserted', []))}")
    print(f"  Deleted: {len(result.get('deleted', []))}")
    print(f"  Skipped: {len(result.get('skipped', []))}")
