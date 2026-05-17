#!/usr/bin/env python3
"""Fetch WEC race calendar from fiawec.com and print JSON list of events.

Usage: python wec_calendar.py [YEAR] [--upload --creds CRED.json --calendar-id ID]
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import List

import requests
from bs4 import BeautifulSoup

BASE = "https://www.fiawec.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_wec_calendar(year: int) -> List[dict]:
    sess = requests.Session()
    sess.headers.update(HEADERS)

    url = f"{BASE}/en/"
    resp = sess.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Find candidate race links (/en/race/...)
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Skip summary pages and archive links that don't contain schedule info
        if "/en/race/" in href and "/summary/" not in href and "/race/summary" not in href:
            full = href if href.startswith("http") else BASE + href
            if full not in seen:
                seen.add(full)
                links.append((full, a.get_text(" ", strip=True)))

    events = []
    months = {m[:3].title(): i for i, m in enumerate(
        ["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}

    for link, anchor_text in links:
        title = anchor_text or link.rstrip("/").split("/")[-1].replace("-", " ").title()

        # Try to fetch the event page early so we can prefer the page title (race name)
        ps = None
        try:
            rpage = sess.get(link, timeout=30)
            rpage.raise_for_status()
            ps = BeautifulSoup(rpage.text, "html.parser")
        except Exception:
            ps = None

        # Prefer structured page title (og:title, twitter:title), <title>, or headings/classed elements
        if ps is not None:
            ptitle = None

            # meta property or name
            for prop in ("og:title", "twitter:title"):
                tag = ps.find("meta", {"property": prop}) or ps.find("meta", {"name": prop})
                if tag and tag.get("content"):
                    ptitle = tag.get("content").strip()
                    break

            # fallback to document <title>
            if not ptitle and ps.title and ps.title.string:
                ptitle = ps.title.string.strip()

            # headings (h1..h3)
            if not ptitle:
                best_h = None
                for tagname in ("h1", "h2", "h3"):
                    for h in ps.find_all(tagname):
                        txt = h.get_text(" ", strip=True)
                        if not txt:
                            continue
                        # prefer a heading that's longer than short date-like anchors
                        if best_h is None or len(txt) > len(best_h):
                            best_h = txt
                if best_h:
                    ptitle = best_h

            # elements whose class or id suggests a title (class contains 'title'|'race'|'event'|'heading')
            if not ptitle:
                for tag in ps.find_all(True, attrs={"class": True}):
                    cls = " ".join(tag.get("class") or [])
                    if re.search(r"\b(title|race|event|heading|headline)\b", cls, re.I):
                        txt = tag.get_text(" ", strip=True)
                        if txt:
                            ptitle = txt
                            break

            # Helper to detect date-like strings (e.g. '9 May', 'BEL 9 May')
            def looks_like_date(s: str) -> bool:
                if not s:
                    return False
                if re.search(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\b", s, re.I):
                    return True
                if re.search(r"\b\d{1,2}/\d{1,2}\b", s):
                    return True
                return False

            # If the anchor_text looks like a short date (e.g. 'BEL 9 May'), prefer the page title when available
            if ptitle and (looks_like_date(anchor_text) or len(anchor_text) < 10):
                title = ptitle
            else:
                # otherwise only replace if the page title is meaningfully different from the anchor
                if ptitle and ptitle.strip() and ptitle.strip().lower() != anchor_text.strip().lower():
                    title = ptitle

        # Try to parse a day+month from anchor text like 'ITA 14 APR' or '14 Apr'
        dt_date = None
        m = re.search(r"(\d{1,2})\s*([A-Za-z]{3,})", anchor_text)
        if m:
            try:
                day = int(m.group(1))
                mon = m.group(2)[:3].title()
                mon_i = months.get(mon)
                if mon_i:
                    # determine year: prefer year mentioned in anchor_text or in URL, fallback to requested year
                    y = None
                    ytxt = re.search(r"(20\d{2})", anchor_text)
                    if ytxt:
                        try:
                            y = int(ytxt.group(1))
                        except Exception:
                            y = None
                    if y is None:
                        yurl = re.search(r"(20\d{2})", link)
                        if yurl:
                            try:
                                y = int(yurl.group(1))
                            except Exception:
                                y = None
                    if y is None:
                        y = year
                    dt_date = date(y, mon_i, day)
            except Exception:
                dt_date = None

        # If not found yet, try to extract date information from the fetched page (if available)
        if dt_date is None and ps is not None:
            # 1) Try meta tags commonly used for published/updated dates
            found = None
            meta_props = ["article:published_time", "og:updated_time"]
            meta_names = ["pubdate", "datePublished", "date", "publishdate"]
            for pname in meta_props:
                tag = ps.find("meta", {"property": pname})
                if tag and tag.get("content"):
                    found = tag.get("content")
                    break
            if not found:
                for nname in meta_names:
                    tag = ps.find("meta", {"name": nname})
                    if tag and tag.get("content"):
                        found = tag.get("content")
                        break

            if found:
                try:
                    dt = datetime.fromisoformat(found)
                    dt_date = dt.date()
                except Exception:
                    mm = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", found)
                    if mm:
                        try:
                            day = int(mm.group(1))
                            mon = mm.group(2)[:3].title()
                            mon_i = months.get(mon)
                            yr = int(mm.group(3))
                            if mon_i:
                                dt_date = date(yr, mon_i, day)
                        except Exception:
                            dt_date = None

            # 2) Fallback: search visible text for a full date with year
            if dt_date is None:
                text = ps.get_text(" ", strip=True)
                m2 = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
                if m2:
                    try:
                        day = int(m2.group(1))
                        mon = m2.group(2)[:3].title()
                        mon_i = months.get(mon)
                        yr = int(m2.group(3))
                        if mon_i:
                            dt_date = date(yr, mon_i, day)
                    except Exception:
                        dt_date = None

            # 3) Last resort: look for a <time datetime="..."> on the page
            if dt_date is None:
                ttag = ps.find("time")
                if ttag and ttag.get("datetime"):
                    try:
                        dt = datetime.fromisoformat(ttag.get("datetime"))
                        dt_date = dt.date()
                    except Exception:
                        pass

        # attempt to determine event year from URL (preferred) or date
        event_year = None
        yurl = re.search(r"(20\d{2})", link)
        if yurl:
            try:
                event_year = int(yurl.group(1))
            except Exception:
                event_year = None
        if event_year is None and dt_date is not None:
            try:
                event_year = dt_date.year
            except Exception:
                event_year = None

        events.append({
            "summary": title,
            "date": dt_date.isoformat() if dt_date else None,
            "url": link,
            "event_year": event_year,
        })

    # Deduplicate by normalized summary+event_year (keep same event across years separate)
    def norm(s: str) -> str:
        if not s:
            return ""
        import re
        s2 = s.lower()
        s2 = re.sub(r"\s+", " ", s2).strip()
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


def wec_events_to_gcal(events: List[dict], color_id: str = "10") -> List[dict]:
    gcal = []
    for ev in events:
        # Ensure we create all-day events. Accept 'date' or 'start.dateTime' input.
        d = ev.get("date") or (ev.get("start") or {}).get("date") or (ev.get("start") or {}).get("dateTime")
        if not d:
            continue
        try:
            # If datetime string present, extract date part
            if "T" in d:
                dt = datetime.fromisoformat(d)
                start_date = dt.date()
            else:
                # pure date like YYYY-MM-DD
                start_date = date.fromisoformat(d)
        except Exception:
            # fallback parse
            try:
                y, m, day = map(int, d.split("-"))
                start_date = date(y, m, day)
            except Exception:
                continue

        end_date = (start_date + timedelta(days=1)).isoformat()

        gcal.append({
            "summary": ev.get("summary"),
            "start": {"date": start_date.isoformat()},
            "end": {"date": end_date},
            "description": ev.get("url"),
            "colorId": color_id,
        })
    return gcal


def insert_events(service, calendar_id: str, events: list[dict], color_id: str = "10") -> dict:
    """Insert/update/delete events in Google Calendar similar to F1 script behavior.

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
    parser = argparse.ArgumentParser(description="Fetch WEC calendar and optionally upload to Google Calendar")
    parser.add_argument("year", nargs="?", default=2026, type=int)
    parser.add_argument("--upload", action="store_true", help="Upload generated events to Google Calendar")
    parser.add_argument("--calendar-id", default=None, help="Target Google Calendar ID")
    parser.add_argument("--creds", default="calendarcred.json", help="Path to service account JSON credentials")
    parser.add_argument("--include-other", action="store_true", help="Include events from other years (default: only the requested year)")
    parser.add_argument("--color-id", default="10", help="Google Calendar colorId to apply to events")
    args = parser.parse_args()

    year = args.year
    evs = fetch_wec_calendar(year)

    # By default, only keep events for the requested year. Use --include-other to include others.
    if not args.include_other:
        evs = [e for e in evs if e.get('event_year') == year]

    if not args.upload:
        print(json.dumps(evs, indent=2, ensure_ascii=False))
        raise SystemExit(0)

    # prepare gcal payloads
    gcal_events = wec_events_to_gcal(evs, color_id=args.color_id)

    # Google API libs optional
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
