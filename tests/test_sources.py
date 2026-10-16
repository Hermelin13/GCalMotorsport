from datetime import datetime, timezone
import pytest
from motorsport.model import RaceEvent
from motorsport.sources import category, from_ics, deduplicate
from motorsport.google_calendar import event_body, changed

def test_f1_filter():
    assert category('F1', 'Monaco Sprint Qualifying') == 'sprint-qualifying'
    assert category('F1', 'Monaco Sprint Race') == 'sprint'
    assert category('F1', 'Monaco Qualifying') == 'qualifying'
    assert category('F1', 'Monaco Grand Prix') == 'race'
    assert category('F1', 'Monaco Free Practice 1') is None

def test_nonf1_filter():
    assert category('WEC', '24 Hours of Le Mans Race') == 'race'
    assert category('WEC', 'Le Mans Qualifying') is None
    assert category('FORMULA_E', 'Berlin E-Prix Race 1') == 'race'
    assert category('DAYTONA', 'Roar Before The Rolex 24') is None

def test_all_day_skipped():
    ics = b'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nSUMMARY:24h Nurburgring Race\r\nDTSTART;VALUE=DATE:20270529\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
    assert from_ics('NURBURGRING', ics, 'https://example.com') == []

def test_event_is_two_hours_and_stable():
    e = RaceEvent('F1', '2027:monaco:race', 'Monaco Race', datetime(2027, 6, 6, 13, tzinfo=timezone.utc), 'https://example.com')
    data = event_body(e)
    assert data['colorId'] == '10'
    assert 'eventLabelId' not in data
    assert data['start']['dateTime'].startswith('2027-06-06T15:00')
    assert data['end']['dateTime'].startswith('2027-06-06T17:00')
    assert len(deduplicate([e, e])) == 1
    assert changed(data, data) is False
