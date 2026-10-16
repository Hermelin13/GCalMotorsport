"""Conservative automatic sources: never turn a race weekend into a made-up race start."""
from __future__ import annotations
import json
import re
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import requests
from .model import RaceEvent

AGENT = {'User-Agent': 'MotorsportCalendar/3.0 (+personal calendar sync)'}
JOLPICA = 'https://api.jolpi.ca/ergast/f1/{year}.json?limit=100'
MOTODB_FE = 'https://raw.githubusercontent.com/vishwapramuditha/moto-db/main/data/formula_e/{year}/schedule.json'
MOTODB_WEC = 'https://raw.githubusercontent.com/vishwapramuditha/moto-db/main/data/wec/{year}/schedule.json'
OFFICIAL = {
    'FORMULA_E': 'https://www.fiaformulae.com/en/calendar',
    'NURBURGRING': 'https://www.24h-rennen.de/',
    'DAYTONA': 'https://www.imsa.com/events/{year}-rolex-24-at-daytona/',
}


def get(url, session=requests):
    response = session.get(url, headers=AGENT, timeout=30)
    response.raise_for_status()
    if len(response.content) > 5_000_000:
        raise ValueError('Source response is too large')
    return response


def parse_instant(day, clock):
    if not day or not clock or not re.fullmatch(r'\d\d:\d\d:\d\dZ', str(clock)):
        return None
    return datetime.fromisoformat(f'{day}T{clock[:-1]}+00:00')


def f1_from_json(data, url):
    output = []
    for race in data['MRData']['RaceTable']['Races']:
        season = race['season']; round_ = race['round']; name = race['raceName']
        kinds = [('SprintQualifying', 'Sprint kvalifikace'), ('Sprint', 'Sprint'),
                 ('Qualifying', 'Kvalifikace'), (None, 'Závod')]
        for field, label in kinds:
            obj = race.get(field) if field else race
            if not obj:
                continue
            start = parse_instant(obj.get('date'), obj.get('time'))
            if start:
                kind = field or 'Race'
                output.append(RaceEvent('F1', f'{season}:round-{round_}:{kind}',
                                        f'F1 | {name} – {label}', start, url))
    return output


def fetch_f1(year, session=requests):
    url = JOLPICA.format(year=year)
    return f1_from_json(get(url, session).json(), url)


def wec_from_json(data, url):
    output = []
    for race in data['races']:
        name = race.get('name', '')
        if 'prologue' in name.lower() or 'test' in name.lower():
            continue
        sessions = [s for s in race.get('sessions', []) if re.match(r'^race(?:\s|-|$)', s.get('name', ''), re.I)]
        if len(sessions) != 1:
            continue
        timestamp = sessions[0].get('date')
        if not timestamp:
            continue
        start = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        if start.tzinfo is None or start.hour == 0 and start.minute == 0:
            # Midnight timestamps in upstream feeds may be date-only placeholders.
            continue
        race_id = race.get('race_id') or race.get('slug')
        if not race_id:
            continue
        output.append(RaceEvent('WEC', str(race_id), name, start, race.get('url', url)))
    return output


def fetch_wec(year, session=requests):
    url = MOTODB_WEC.format(year=year)
    try:
        r = get(url, session)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return []  # New season not published in MotoDB yet.
        raise
    return wec_from_json(r.json(), url)


def as_all_day(series, key, title, day, source):
    return RaceEvent(series, key, title, datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc), source, day)


def formula_e_from_json(data, url, year=None):
    """MotoDB has one row per race (double headers therefore yield two days)."""
    out = []
    if not isinstance(data, list):
        raise ValueError('Invalid Formula E feed schema')
    for item in data:
        try:
            day = datetime.strptime(item['date'], '%d %B %Y').date()
            round_ = int(item['round'])
        except (ValueError, TypeError, KeyError):
            continue
        if year and day.year not in (year, year - 1):
            continue  # FE season crosses calendar years
        out.append(as_all_day('FORMULA_E', f'{year or day.year}:round-{round_}',
                              f"Formula E | {item.get('eprix', 'E-Prix')} – závod", day, url))
    return out


def fetch_formula_e(year, session=requests):
    # MotoDB uses season END year: a 2026 season may start in December 2025.
    url = MOTODB_FE.format(year=year)
    try:
        response = get(url, session)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return []
        raise
    return formula_e_from_json(response.json(), url, year)


def _end_of_weekend_to_race_day(end_day):
    """For a published Thu–Sun 24-hour meeting the main race starts Saturday.

    This is a conventional calendar-day marker, NOT an asserted start time.
    """
    return end_day - timedelta(days=1)


def fetch_nurburgring(year, session=requests):
    url = 'https://www.24h-rennen.de/termine/'
    html = BeautifulSoup(get(url, session).text, 'html.parser').get_text(' ', strip=True)
    section = html.split('24h Nürburgring Qualifiers')[0]
    matches = re.findall(r'(\d{1,2})\.\s*[–-]\s*(\d{1,2})\.(\d{2})\.(20\d{2})', section)
    out = []
    for start_day, end_day, month, found_year in matches:
        if int(found_year) != year:
            continue
        end = date(year, int(month), int(end_day))
        if (end - date(year, int(month), int(start_day))).days < 2:
            continue
        out.append(as_all_day('NURBURGRING', f'{year}:24h',
                              '24h Nürburgring – závod', _end_of_weekend_to_race_day(end), url))
    return out


def fetch_daytona(year, session=requests):
    url = f'https://www.imsa.com/events/{year}-rolex-24-at-daytona/'
    html = BeautifulSoup(get(url, session).text, 'html.parser').get_text(' ', strip=True)
    # IMSA WHEN: Thursday, January 28, 2027 to Sunday, January 31, 2027
    pattern = r'WHEN\s*:?\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Za-z]+)\s+\d{1,2},?\s+('+str(year)+r')\s+to\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Za-z]+)\s+(\d{1,2}),?\s+('+str(year)+r')'
    match = re.search(pattern, html, re.I)
    if not match:
        return []
    month = match.group(3)
    end = datetime.strptime(f'{month} {match.group(4)} {year}', '%B %d %Y').date()
    return [as_all_day('DAYTONA', f'{year}:rolex-24', '24h Daytona – závod',
                       _end_of_weekend_to_race_day(end), url)]


def _walk_jsonld(obj):
    if isinstance(obj, list):
        for item in obj:
            yield from _walk_jsonld(item)
    elif isinstance(obj, dict):
        yield obj
        for value in obj.values():
            if isinstance(value, (dict, list)):
                yield from _walk_jsonld(value)


def official_jsonld(series, html, url):
    """Only use structured race startDate containing an explicit timezone and time.

    Publication of a weekend/date without a race start is deliberately not used.
    """
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    for node in soup.find_all('script', type='application/ld+json'):
        try:
            obj = json.loads(node.string or node.get_text())
        except (ValueError, TypeError):
            continue
        for item in _walk_jsonld(obj):
            types = item.get('@type', [])
            if isinstance(types, str):
                types = [types]
            if not any(x in types for x in ('SportsEvent', 'Event')):
                continue
            title = str(item.get('name', ''))
            low = title.lower()
            if any(k in low for k in ('qualifying', 'practice', 'prologue', 'roar before', 'test')):
                continue
            if series == 'FORMULA_E' and not any(k in low for k in ('e-prix', 'eprix', 'race')):
                continue
            if series == 'NURBURGRING' and not ('24h' in low or '24 hour' in low or '24 stunden' in low):
                continue
            if series == 'DAYTONA' and not any(k in low for k in ('rolex 24', '24h daytona', '24 hours of daytona')):
                continue
            raw = item.get('startDate')
            if not isinstance(raw, str):
                continue
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
                day = date.fromisoformat(raw)
                uid = str(item.get('identifier') or item.get('url') or title).lower()
                uid = re.sub(r'[^a-z0-9]+', '-', uid).strip('-')[-150:]
                results.append(as_all_day(series, f'{day.year}:{uid}', f'{series.replace("_", " ")} | {title}', day, url))
                continue
            try:
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            except ValueError:
                continue
            if dt.tzinfo is None or dt.utcoffset() is None:
                continue
            # An all-day midnight timestamp is often a schema.org placeholder.
            if dt.hour == 0 and dt.minute == 0:
                continue
            # stable identity independent from exact start time
            uid = str(item.get('identifier') or item.get('url') or title).lower()
            uid = re.sub(r'[^a-z0-9]+', '-', uid).strip('-')[-150:]
            key = f'{dt.year}:{uid}'
            results.append(RaceEvent(series, key, f'{series.replace("_", " ")} | {title}', dt, url))
    return results


def fetch_official(series, year, session=requests):
    url = OFFICIAL[series].format(year=year)
    return official_jsonld(series, get(url, session).text, url)


def load_all(years, session=requests):
    """Return (events, errors, pending). A source with no exact time is pending, not a guessed event."""
    events, failures, pending = [], [], []
    for year in sorted(years):
        for series, loader in [('F1', fetch_f1), ('WEC', fetch_wec),
                               ('FORMULA_E', fetch_formula_e),
                               ('DAYTONA', fetch_daytona),
                               ('NURBURGRING', fetch_nurburgring)]:
            try:
                found = loader(year, session)
                events.extend(found)
                if not found:
                    pending.append(f'{series} {year}: zatím nejsou dostupná ověřená data závodu')
            except Exception as exc:
                failures.append(f'{series} {year}: {type(exc).__name__}: {exc}')
    return events, failures, pending
