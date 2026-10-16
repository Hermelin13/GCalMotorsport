"""Feeds require an actual timed start, never a guessed race-weekend date."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
import re
from pathlib import Path
import requests
from icalendar import Calendar
from .model import RaceEvent

SERIES = {"F1", "FORMULA_E", "WEC", "NURBURGRING", "DAYTONA"}
F1_KINDS = (("sprint qualifying", "sprint-qualifying"), ("sprint shootout", "sprint-qualifying"),
            ("sprint race", "sprint"), ("sprint", "sprint"), ("qualifying", "qualifying"), ("race", "race"))


def category(series: str, title: str) -> str | None:
    t = re.sub(r"\s+", " ", title.lower())
    if series == "F1":
        if any(s in t for s in ("practice", "testing", "free practice", "press conference")):
            return None
        for phrase, kind in F1_KINDS:
            if phrase in t or (kind == "race" and "grand prix" in t):
                return kind
        return None
    if series in {"NURBURGRING", "DAYTONA"}:
        if any(x in t for x in ("qualif", "practice", "test", "roar", "support", "warm up")):
            return None
        if series == "NURBURGRING":
            return "race" if ("24h" in t or "24 hour" in t or "24 stunden" in t) else None
        return "race" if ("rolex 24" in t or "24h daytona" in t or "24 hours of daytona" in t) else None
    if any(x in t for x in ("qualif", "practice", "hyperpole", "warm up", "prologue", "test", "shootout")):
        return None
    if series == "FORMULA_E":
        return "race" if ("e-prix" in t or "eprix" in t or "race" in t) else None
    return "race" if ("race" in t or "hours" in t or "heures" in t or "1812" in t or "lone star le mans" in t) else None


def _time(v):
    """icalendar decoded DTSTART can be date or datetime; dates must not be guessed."""
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None or v.utcoffset() is None:
        return None
    return v


def _name_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:110]


def from_ics(series: str, content: bytes, source: str) -> list[RaceEvent]:
    cal = Calendar.from_ical(content)
    events = []
    # Formula E double headers need separate identifiers even at same venue.
    for c in cal.walk("VEVENT"):
        title = str(c.get("SUMMARY", "")).strip()
        kind = category(series, title)
        if not kind:
            continue
        start = _time(c.decoded("DTSTART"))
        if not start:
            continue
        # Prefer stable UID. Some feeds regenerate UIDs; match by title+year instead for a single race.
        # For double headers, an explicit 'race 1/2' suffix or UID is needed to avoid collisions.
        day_part = re.search(r"\b(?:race|round)\s*([12])\b", title, re.I)
        identity = _name_key(title) + ("-" + day_part.group(1) if day_part else "")
        key = f"{start.year}:{identity}:{kind}"
        events.append(RaceEvent(series, key, f"{series.replace('_', ' ')} | {title}", start, source))
    return events


def fetch_ics(series: str, url: str, session=requests) -> list[RaceEvent]:
    if not url.startswith("https://"):
        raise ValueError(f"{series}: feed must use HTTPS")
    response = session.get(url, timeout=30, headers={"User-Agent": "MotorsportCalendar/2.0"})
    response.raise_for_status()
    if len(response.content) > 5_000_000:
        raise ValueError(f"{series}: ICS feed too large")
    if b"BEGIN:VCALENDAR" not in response.content[:300]:
        raise ValueError(f"{series}: response is not an ICS calendar")
    return from_ics(series, response.content, url)


def load_overrides(path: str) -> list[RaceEvent]:
    if not Path(path).exists():
        return []
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Overrides must be a JSON array")
    result = []
    for row in raw:
        if row["series"] not in SERIES:
            raise ValueError(f"Unknown series: {row['series']}")
        start = datetime.fromisoformat(row["start"].replace("Z", "+00:00"))
        result.append(RaceEvent(row["series"], row["key"], row["title"], start, row["source"]))
    return result


def deduplicate(events: list[RaceEvent]) -> list[RaceEvent]:
    result = {}
    for e in events:
        if e.stable_id in result and result[e.stable_id] != e:
            raise ValueError(f"Conflicting events with same key: {e.series}/{e.key}")
        result[e.stable_id] = e
    return list(result.values())
