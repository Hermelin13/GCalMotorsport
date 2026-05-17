import requests
import datetime

def fetch_f1_calendar(year):
    monaco = {
        "summary": "Formula 1 Monaco Grand Prix 2026",
        "sessions": {
            "p1": "2026-05-22T13:30:00Z",
            "p2": "2026-05-22T17:00:00Z",
            "p3": "2026-05-23T12:30:00Z",
            "qualifying": "2026-05-23T16:00:00Z",
            "race": "2026-05-24T15:00:00Z"
        }
    }
    canada = {
        "summary": "Formula 1 Canadian Grand Prix 2026",
        "sessions": {
            "p1": "2026-06-12T17:30:00Z",
            "p2": "2026-06-12T21:00:00Z",
            "p3": "2026-06-13T16:30:00Z",
            "qualifying": "2026-06-13T20:00:00Z",
            "race": "2026-06-14T18:00:00Z"
        }
    }
    return [monaco, canada]

def sessions_to_gcal_events(events):
    gcal_events = []
    for event in events:
        summary = event.get("summary")
        sessions = event.get("sessions", {})
        for session_name, start_time in sessions.items():
            gcal_events.append({
                "summary": f"{summary} - {session_name}",
                "start": {"dateTime": start_time},
                "end": {"dateTime": start_time}
            })
    return gcal_events
