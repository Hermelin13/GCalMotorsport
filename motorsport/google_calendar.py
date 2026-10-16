from datetime import timedelta, timezone
from zoneinfo import ZoneInfo
from google.oauth2 import service_account
from googleapiclient.discovery import build
from .model import RaceEvent

SCOPE = ["https://www.googleapis.com/auth/calendar.events"]
BASIL_COLOR_ID = "10"


def service_from_env(env):
    import base64, json
    if env.get("GOOGLE_CREDENTIALS_B64"):
        data = json.loads(base64.b64decode(env["GOOGLE_CREDENTIALS_B64"], validate=True))
        creds = service_account.Credentials.from_service_account_info(data, scopes=SCOPE)
    elif env.get("GOOGLE_CREDENTIALS_FILE"):
        creds = service_account.Credentials.from_service_account_file(env["GOOGLE_CREDENTIALS_FILE"], scopes=SCOPE)
    else:
        raise ValueError("Google credentials not configured")
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def event_body(e: RaceEvent, zone="Europe/Prague"):
    start = e.start.astimezone(ZoneInfo(zone))
    end = start + timedelta(hours=2)
    if e.all_day is not None:
        start_value = {"date": e.all_day.isoformat()}
        end_value = {"date": (e.all_day + timedelta(days=1)).isoformat()}
    else:
        start_value = {"dateTime": start.isoformat(), "timeZone": zone}
        end_value = {"dateTime": end.isoformat(), "timeZone": zone}
    body = {
        "id": e.stable_id,
        "colorId": BASIL_COLOR_ID,
        "summary": e.title,
        "description": f"Série: {e.series}\nOficiální/publikovaný zdroj: {e.source}\nZobrazení: jeden celý den (pokud není čas závodu potvrzen) nebo 2 h od startu.",
        "start": start_value,
        "end": end_value,
        "extendedProperties": {"private": {"motorsport_sync": "v2", "race_key": f"{e.series}:{e.key}"}},
    }
    return body


def list_managed(service, calendar_id, years):
    result = {}
    for year in years:
        token = None
        while True:
            reply = service.events().list(
                calendarId=calendar_id, timeMin=f"{year}-01-01T00:00:00Z",
                timeMax=f"{year+1}-01-01T00:00:00Z", maxResults=2500,
                privateExtendedProperty="motorsport_sync=v2", pageToken=token,
                singleEvents=True,
            ).execute()
            for item in reply.get("items", []):
                if item.get("status") != "cancelled":
                    result[item["id"]] = item
            token = reply.get("nextPageToken")
            if not token:
                break
    return result


def changed(before, after):
    return any(before.get(k) != after.get(k) for k in
               ("summary", "description", "start", "end", "colorId"))


def synchronize(service, calendar_id, events, dry_run=False, zone="Europe/Prague"):
    if not events:
        return []
    years = {e.start.astimezone(ZoneInfo(zone)).year for e in events}
    existing = list_managed(service, calendar_id, years)
    changes = []
    for e in sorted(events, key=lambda x: x.start):
        body = event_body(e, zone=zone)
        old = existing.get(e.stable_id)
        if old is None:
            changes.append(f"➕ {body['summary']} ({body['start'].get('dateTime', body['start'].get('date'))})")
            if not dry_run:
                service.events().insert(calendarId=calendar_id, body=body).execute()
        elif changed(old, body):
            changes.append(f"🔄 {body['summary']}: {old.get('start', {}).get('dateTime', old.get('start', {}).get('date', '?'))} → {body['start'].get('dateTime', body['start'].get('date'))}")
            if not dry_run:
                # PATCH does not remove attendees/custom user-owned properties.
                patch = {k: v for k, v in body.items() if k != "id"}
                service.events().patch(calendarId=calendar_id, eventId=e.stable_id,
                                       body=patch).execute()
    # Never delete entries just because an upstream website is empty/unavailable.
    return changes
