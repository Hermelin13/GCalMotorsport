from motorsport.auto_sources import f1_from_json, wec_from_json, official_jsonld, formula_e_from_json, fetch_daytona, fetch_nurburgring
from motorsport.google_calendar import event_body


def test_f1_keeps_four_selected_sessions():
    data = {'MRData': {'RaceTable': {'Races': [{
        'season': '2027', 'round': '1', 'raceName': 'Example Grand Prix',
        'date': '2027-03-06', 'time': '15:00:00Z',
        'FirstPractice': {'date': '2027-03-04', 'time': '10:00:00Z'},
        'SprintQualifying': {'date': '2027-03-04', 'time': '15:00:00Z'},
        'Sprint': {'date': '2027-03-05', 'time': '11:00:00Z'},
        'Qualifying': {'date': '2027-03-05', 'time': '15:00:00Z'},
    }]}}}
    result = f1_from_json(data, 'https://source')
    assert len(result) == 4
    assert len({r.stable_id for r in result}) == 4


def test_f1_does_not_guess_missing_times():
    data = {'MRData': {'RaceTable': {'Races': [{
        'season': '2027', 'round': '2', 'raceName': 'Example GP', 'date': '2027-05-01'
    }]}}}
    assert f1_from_json(data, 'https://source') == []


def test_wec_uses_race_session_not_weekend():
    data = {'races': [{'race_id': '6-hours-example-2027', 'name': '6 Hours Example',
        'date': '2027-04-11T00:00:00+02:00', 'sessions': [
            {'name': 'Qualifying', 'date': '2027-04-10T16:00:00+02:00'},
            {'name': 'Race - 6 Hours Example', 'date': '2027-04-11T13:00:00+02:00'}]}]}
    out = wec_from_json(data, 'https://source')
    assert len(out) == 1
    assert out[0].start.hour == 13


def test_official_page_does_not_invent_time():
    html = '<script type="application/ld+json">{"@type":"SportsEvent","name":"Rolex 24 At DAYTONA","startDate":"2027-01-30"}</script>'
    assert official_jsonld('DAYTONA', html, 'https://source')[0].all_day.isoformat() == '2027-01-30'


def test_formula_e_double_header_all_day():
    sample = [{'round': '4', 'eprix': 'Berlin ePrix', 'date': '2 May 2026'},
              {'round': '5', 'eprix': 'Berlin ePrix', 'date': '3 May 2026'}]
    races = formula_e_from_json(sample, 'https://source', 2026)
    assert len(races) == 2
    assert races[0].all_day.isoformat() == '2026-05-02'
    assert event_body(races[0])['start'] == {'date': '2026-05-02'}
    assert event_body(races[0])['end'] == {'date': '2026-05-03'}


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.content = text.encode()
    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, body):
        self.body = body
    def get(self, *a, **kw):
        return FakeResponse(self.body)


def test_daytona_calendar_day_from_official_weekend():
    text = 'WHEN: Thursday, January 28, 2027 to Sunday, January 31, 2027'
    out = fetch_daytona(2027, FakeSession(text))
    assert len(out) == 1
    assert out[0].all_day.isoformat() == '2027-01-30'


def test_nurburgring_calendar_day_from_official_weekend():
    text = 'ADAC RAVENOL 24h Nürburgring 14. – 17.05.2026 27. – 30.05.2027 25. – 28.05.2028 ADAC 24h Nürburgring Qualifiers'
    out = fetch_nurburgring(2027, FakeSession(text))
    assert len(out) == 1
    assert out[0].all_day.isoformat() == '2027-05-29'
