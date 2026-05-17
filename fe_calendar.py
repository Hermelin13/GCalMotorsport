#!/usr/bin/env python3
"""Fetch Formula E calendar from fiaformulae.com and print JSON list of events.

Usage: python fe_calendar.py [SEASON] [--upload --creds CRED.json --calendar-id ID]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta
from typing import List

import requests
from bs4 import BeautifulSoup

BASE = "https://fiaformulae.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_fe_calendar(season: str) -> List[dict]:
    sess = requests.Session()
    sess.headers.update(HEADERS)

    url = f"{BASE}/en/calendar"
    resp = sess.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    months = {m[:3].title(): i for i, m in enumerate(
        ["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}

    def extract_race_datetime(soup_obj, default_year=None):
        """Return a datetime for the RACE session if found, else None."""
        page_text = soup_obj.get_text(" ", strip=True)

        # 1) Prefer explicit <time datetime="..."> tags
        for ttag in soup_obj.find_all("time"):
            dtstr = ttag.get("datetime")
            if dtstr:
                try:
                    return datetime.fromisoformat(dtstr)
                except Exception:
                    continue

        # 2) Find session-labelled times and prefer RACE
        session_pat = re.compile(
            r"(?:(\d{1,2})\s*([A-Za-z]+)\s*(\d{4})?)?\s*(PRACTICE|QUALIFYING|RACE|RACE\s*DAY|MAIN)\s*[:\s\-–]*?(\d{1,2}:\d{2})",
            re.IGNORECASE,
        )
        found = None
        for m in session_pat.finditer(page_text):
            day_g, mon_g, year_g, sess_name, time_s = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            if not sess_name:
                continue
            if sess_name.strip().upper().find('RACE') == -1 and sess_name.strip().upper() != 'MAIN':
                # skip practice/qualifying unless no race found
                if found is not None:
                    continue
            # resolve month and year
            try:
                if mon_g:
                    mon = mon_g[:3].title()
                    mon_i = months.get(mon)
                else:
                    mon_i = None
                if year_g:
                    yr = int(year_g)
                else:
                    yr = default_year
                if day_g and mon_i and yr:
                    hh, mm = map(int, time_s.split(':'))
                    cand = datetime(yr, mon_i, int(day_g), hh, mm)
                    # prefer RACE sessions
                    if sess_name.strip().upper().find('RACE') != -1 or sess_name.strip().upper() == 'MAIN':
                        return cand
                    if found is None:
                        found = cand
            except Exception:
                continue

        if found:
            return found

        # 3) Fallback: ISO date with optional time anywhere on page
        m = re.search(r"(20\d{2})-(\d{2})-(\d{2})(?:[T\s](\d{2}:\d{2}))?", page_text)
        if m:
            try:
                yr = int(m.group(1)); mo = int(m.group(2)); da = int(m.group(3))
                if m.group(4):
                    hh, mins = map(int, m.group(4).split(':'))
                    return datetime(yr, mo, da, hh, mins)
                return datetime(yr, mo, da)
            except Exception:
                return None

        return None

    # Try to parse JSON-LD data first (some pages embed the calendar in a script)
    try:
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '')
            except Exception:
                continue
            # look for itemListElement pattern
            items = None
            if isinstance(data, dict) and data.get('itemListElement'):
                items = data.get('itemListElement')
            # sometimes the JSON-LD is wrapped in a list
            if items is None and isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and entry.get('itemListElement'):
                        items = entry.get('itemListElement')
                        break

            if items:
                for it in items:
                    it_item = it.get('item') or it
                    name = it_item.get('name') or it_item.get('headline') or ''
                    start = it_item.get('startDate') or it_item.get('datePublished')
                    url_ev = it_item.get('url') or it_item.get('@id') or ''
                    # normalize
                    dt_obj = None
                    if start:
                        try:
                            # if JSON-LD start likely represents the race, keep it
                            dt_obj = datetime.fromisoformat(start)
                        except Exception:
                            # try date-only or attempt to extract race session from the referenced URL
                            try:
                                dt_obj = datetime.fromisoformat(start+'T00:00:00')
                            except Exception:
                                # try to fetch referenced URL to find race time
                                if url_ev:
                                    try:
                                        r2 = sess.get(url_ev, timeout=20)
                                        r2.raise_for_status()
                                        ps2 = BeautifulSoup(r2.text, 'html.parser')
                                        dt_obj = extract_race_datetime(ps2)
                                    except Exception:
                                        dt_obj = None
                                else:
                                    dt_obj = None

                    event_year = None
                    yurl = re.search(r"(20\d{2})", url_ev)
                    if yurl:
                        try:
                            event_year = int(yurl.group(1))
                        except Exception:
                            event_year = None
                    if event_year is None and dt_obj is not None:
                        try:
                            event_year = dt_obj.year
                        except Exception:
                            event_year = None

                    events.append({
                        'summary': name,
                        'dateTime': dt_obj.isoformat() if dt_obj else None,
                        'date': dt_obj.date().isoformat() if dt_obj else None,
                        'url': url_ev,
                        'event_year': event_year,
                    })
                # if we found items via JSON-LD, skip link parsing
                if events:
                    # dedupe and return
                    def norm(s: str) -> str:
                        if not s:
                            return ''
                        return re.sub(r"\s+", ' ', s.lower()).strip()
                    seen = set(); unique = []
                    for ev in events:
                        key = (norm(ev.get('summary')), ev.get('event_year'))
                        if key in seen:
                            continue
                        seen.add(key); unique.append(ev)
                    return unique
    except Exception:
        pass

    # Fallback: extract race links from raw HTML using regex (some sites render anchors via JS)
    raw = resp.text
    pattern = re.compile(r"(/en/calendar/\d{4}-\d{2}/r\d+-[a-z0-9-]+)", re.IGNORECASE)
    found_links = set(m.group(1) for m in pattern.finditer(raw))
    for rel in sorted(found_links):
        full = rel if rel.startswith('http') else BASE + rel
        if full in [e.get('url') for e in events]:
            continue
        # fetch detail page
        try:
            r = sess.get(full, timeout=30)
            r.raise_for_status()
            ps = BeautifulSoup(r.text, 'html.parser')
            title = ps.find('h1') or ps.title
            title_text = title.get_text(' ', strip=True) if title else full.split('/')[-1].replace('-', ' ').title()
            # attempt to find RACE session datetime
            dt_obj = extract_race_datetime(ps, default_year=None)

            event_year = None
            yurl = re.search(r"(20\d{2})", full)
            if yurl:
                try:
                    event_year = int(yurl.group(1))
                except Exception:
                    event_year = None
            if event_year is None and dt_obj is not None:
                try:
                    event_year = dt_obj.year
                except Exception:
                    event_year = None

            events.append({
                'summary': title_text,
                'dateTime': dt_obj.isoformat() if dt_obj else None,
                'date': dt_obj.date().isoformat() if dt_obj else None,
                'url': full,
                'event_year': event_year,
            })
        except Exception:
            continue

    links = []
    seen = set()
    # calendar page links look like /en/calendar/2025-26/r14-tokyo
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/en/calendar/" in href and "/r" in href:
            full = href if href.startswith("http") else BASE + href
            if full not in seen:
                seen.add(full)
                links.append((full, a.get_text(" ", strip=True)))

    events = []
    months = {m[:3].title(): i for i, m in enumerate(
        ["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}

    for link, anchor in links:
        title = anchor or link.rstrip("/").split("/")[-1].replace("-", " ").title()

        # Try to get date and time from the event page (prefer RACE session)
        dt_obj = None
        try:
            r = sess.get(link, timeout=30)
            r.raise_for_status()
            ps = BeautifulSoup(r.text, "html.parser")
            dt_obj = extract_race_datetime(ps)
        except Exception:
            pass

        # determine event_year from link if present
        event_year = None
        yurl = re.search(r"(20\d{2})", link)
        if yurl:
            try:
                event_year = int(yurl.group(1))
            except Exception:
                event_year = None
        if event_year is None and dt_obj is not None:
            try:
                event_year = dt_obj.year
            except Exception:
                event_year = None

        events.append({
            "summary": title,
            "dateTime": dt_obj.isoformat() if dt_obj else None,
            "date": dt_obj.date().isoformat() if dt_obj else None,
            "url": link,
            "event_year": event_year,
        })

    # dedupe by summary+event_year
    def norm(s: str) -> str:
        if not s:
            return ""
        s2 = re.sub(r"\s+", " ", s.lower()).strip()
        return s2

    seen = set()
    unique = []
    for ev in events:
        key = (norm(ev.get("summary")), ev.get("event_year"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ev)

    return unique


def fe_events_to_gcal(events: List[dict], color_id: str = "10") -> List[dict]:
    gcal = []
    for ev in events:
        # prefer precise datetime if available, otherwise create all-day
        dt_s = ev.get("dateTime")
        if dt_s:
            try:
                dt = datetime.fromisoformat(dt_s)
                start = dt.isoformat()
                end = (dt + timedelta(hours=2)).isoformat()
                gcal.append({
                    "summary": ev.get("summary"),
                    "start": {"dateTime": start, "timeZone": "UTC"},
                    "end": {"dateTime": end, "timeZone": "UTC"},
                    "description": ev.get("url"),
                    "colorId": color_id,
                })
                continue
            except Exception:
                pass

        # fallback to all-day
        d = ev.get("date")
        if not d:
            continue
        try:
            y, m, day = map(int, d.split("-"))
            start_date = date(y, m, day)
            end_date = (start_date + timedelta(days=1)).isoformat()
            gcal.append({
                "summary": ev.get("summary"),
                "start": {"date": start_date.isoformat()},
                "end": {"date": end_date},
                "description": ev.get("url"),
                "colorId": color_id,
            })
        except Exception:
            continue

    return gcal


# insert_events function copied from wec_calendar for safe upload behavior
def insert_events(service, calendar_id: str, events: list[dict], color_id: str = "10") -> dict:
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
            try:
                service.events().delete(calendarId=calendar_id, eventId=item_id).execute()
                deleted.append(item_id)
            except Exception as e:
                print(f"Failed to delete event {item_id}:", e)

        if found_same_date:
            skipped.append({"summary": summary, "date": start_dt})
            continue

        body = ev.copy()
        if isinstance(body.get("reminders"), dict):
            body["reminders"] = {"useDefault": False, "overrides": []}
        try:
            created = service.events().insert(calendarId=calendar_id, body=body, sendUpdates='none').execute()
            inserted.append({"summary": created.get("summary"), "id": created.get("id"), "date": start_dt})
        except Exception as e:
            print("Failed to insert event:", e)

    return {"inserted": inserted, "deleted": deleted, "skipped": skipped}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Formula E calendar and optionally upload to Google Calendar")
    parser.add_argument("season", nargs="?", default="2025-26")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Prepare GCal payload and print it without uploading")
    parser.add_argument("--calendar-id", default=None)
    parser.add_argument("--creds", default="calendarcred.json")
    parser.add_argument("--include-other", action="store_true")
    parser.add_argument("--color-id", default="10")
    args = parser.parse_args()

    evs = fetch_fe_calendar(args.season)
    if not args.include_other:
        # parse season like '2025-26' or '2025-2026' into allowed years
        years_allowed = set()
        m = re.match(r"(\d{4})-(\d{2,4})", args.season)
        if m:
            try:
                y1 = int(m.group(1))
                y2_raw = m.group(2)
                if len(y2_raw) == 2:
                    # e.g. '2025-26' -> 2026
                    y2 = int(str(y1)[:2] + y2_raw)
                else:
                    y2 = int(y2_raw)
                years_allowed.update([y1, y2])
            except Exception:
                years_allowed = set()
        if years_allowed:
            evs = [e for e in evs if e.get("event_year") in years_allowed]

    if args.dry_run:
        gcal_events = fe_events_to_gcal(evs, color_id=args.color_id)
        print(json.dumps(gcal_events, indent=2, ensure_ascii=False))
        raise SystemExit(0)

    if not args.upload:
        print(json.dumps(evs, indent=2, ensure_ascii=False))
        raise SystemExit(0)

    gcal_events = fe_events_to_gcal(evs, color_id=args.color_id)

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except Exception:
        print("ERROR: google-auth or google-api-python-client not installed.")
        raise SystemExit(3)

    if args.calendar_id is None:
        print("ERROR: --calendar-id is required when using --upload")
        raise SystemExit(2)

    creds = service_account.Credentials.from_service_account_file(args.creds, scopes=["https://www.googleapis.com/auth/calendar"])
    service = build("calendar", "v3", credentials=creds)

    print(f"Uploading {len(gcal_events)} events to calendar: {args.calendar_id}")

    result = insert_events(service, args.calendar_id, gcal_events, color_id=args.color_id)
    print("Upload summary:")
    print(f"  Inserted: {len(result.get('inserted', []))}")
    print(f"  Deleted: {len(result.get('deleted', []))}")
    print(f"  Skipped: {len(result.get('skipped', []))}")
