"""Scheduling rules independent of Frappe and Google; all comparisons use UTC."""
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo

MODES = ('Online', 'In person')


def default_preferences():
    return {'timezone': 'Asia/Kolkata', 'configured': False,
            'weekly': {m: [[] for _ in range(7)] for m in MODES},
            'exceptions': [], 'places': [], 'calendar_ids': [], 'holiday_calendar_ids': [],
            'max_in_person_per_day': None, 'buffer_minutes': 15, 'travel_mode': 'DRIVE', 'default_place': '',
            'share_travel_estimate': False}


def windows(values):
    if not isinstance(values, list) or len(values) > 4:
        raise ValueError('Use up to four availability windows per day.')
    output = []
    for pair in values:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError('Each window needs a start and end.')
        start, end = [time.fromisoformat(str(v)) for v in pair]
        if start >= end or start.tzinfo or end.tzinfo:
            raise ValueError('Availability windows must end later on the same day.')
        output.append([start.strftime('%H:%M'), end.strftime('%H:%M')])
    output.sort()
    if any(output[i][0] < output[i-1][1] for i in range(1, len(output))):
        raise ValueError('Availability windows must not overlap.')
    return output


def validate_preferences(data):
    if not isinstance(data, dict): raise ValueError('Invalid availability settings.')
    result = default_preferences()
    result['timezone'] = str(data.get('timezone') or 'Asia/Kolkata')
    ZoneInfo(result['timezone'])
    for mode in MODES:
        days = data.get('weekly', {}).get(mode, [[] for _ in range(7)])
        if not isinstance(days, list) or len(days) != 7: raise ValueError('Configure all seven days.')
        result['weekly'][mode] = [windows(day) for day in days]
    exceptions = data.get('exceptions', [])
    if not isinstance(exceptions, list) or len(exceptions) > 180: raise ValueError('Too many date overrides.')
    seen = set()
    for row in exceptions:
        day = date.fromisoformat(row['date']).isoformat()
        mode = row['mode']
        if mode not in MODES or (day, mode) in seen: raise ValueError('Use one override per date and meeting type.')
        seen.add((day, mode))
        result['exceptions'].append({'date': day, 'mode': mode, 'windows': windows(row.get('windows', []))})
    places = data.get('places', [])
    if not isinstance(places, list) or len(places) > 20: raise ValueError('Save up to 20 personal places.')
    seen = set()
    for p in places:
        identity = str(p.get('id') or '')[:80]
        label, address = str(p.get('label') or '').strip(), str(p.get('address') or '').strip()
        if not identity or identity in seen or not label or not address or len(address) > 500 or len(label)>80:
            raise ValueError('Each saved place needs a unique ID, name and address.')
        seen.add(identity)
        result['places'].append({'id': identity, 'label': label, 'address': address})
    result['default_place'] = str(data.get('default_place') or '')
    if result['default_place'] and result['default_place'] not in seen: raise ValueError('Choose a saved departure point.')
    mode = data.get('travel_mode', 'DRIVE')
    if mode not in ('DRIVE', 'WALK', 'TRANSIT', 'BICYCLE', 'TWO_WHEELER'): raise ValueError('Invalid travel mode.')
    result['travel_mode'] = mode
    buffer = int(data.get('buffer_minutes', 15))
    if not 0 <= buffer <= 180: raise ValueError('Arrival buffer must be between 0 and 180 minutes.')
    result['buffer_minutes'] = buffer
    limit = data.get('max_in_person_per_day')
    if limit is not None and limit != '':
        if isinstance(limit, bool) or not str(limit).isdigit() or not 0 <= int(limit) <= 100:
            raise ValueError('Daily in-person meeting limit must be a whole number between 0 and 100, or blank for unlimited.')
        result['max_in_person_per_day'] = int(limit)
    result['share_travel_estimate'] = bool(data.get('share_travel_estimate'))
    ids = data.get('calendar_ids', [])
    if not isinstance(ids, list) or len(ids) > 10 or any(not isinstance(v,str) or not v or len(v)>254 for v in ids):
        raise ValueError('Choose up to ten calendars.')
    result['calendar_ids'] = list(dict.fromkeys(ids))
    holidays = data.get('holiday_calendar_ids', [])
    if not isinstance(holidays, list) or len(holidays)>10 or any(not isinstance(v,str) or not v or len(v)>254 for v in holidays):
        raise ValueError('Choose up to ten holiday calendars.')
    result['holiday_calendar_ids'] = list(dict.fromkeys(holidays))
    result['configured'] = True
    return result


def aware(value, zone):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo: return parsed.astimezone(timezone.utc)
    tz = ZoneInfo(zone)
    local = parsed.replace(tzinfo=tz)
    # Do not silently shift nonexistent times over a daylight-saving transition.
    if local.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) != parsed:
        raise ValueError('This local time does not exist due to daylight saving. Choose another time.')
    return local.astimezone(timezone.utc)


def working_window(preferences, start, end, mode):
    if not preferences.get('configured'): return False
    zone = ZoneInfo(preferences['timezone'])
    local_start, local_end = start.astimezone(zone), end.astimezone(zone)
    if local_start.date() != local_end.date(): return False
    day = local_start.date().isoformat()
    intervals = preferences['weekly'][mode][local_start.weekday()]
    for override in preferences['exceptions']:
        if override['date'] == day and override['mode'] == mode: intervals = override['windows']; break
    return any(time.fromisoformat(a) <= local_start.time().replace(tzinfo=None)
               and local_end.time().replace(tzinfo=None) <= time.fromisoformat(b) for a,b in intervals)


def overlaps(start, end, periods):
    return any(start < b and end > a for a,b in periods)


def candidate_status(person, start, end, mode):
    if person.get('calendar_error') or not person['preferences'].get('configured'): return 'unknown'
    if mode == 'In person':
        limit = person['preferences'].get('max_in_person_per_day')
        day = start.astimezone(ZoneInfo(person['preferences']['timezone'])).date().isoformat()
        if limit is not None and person.get('daily_counts', {}).get(day, 0) >= limit:
            return 'daily_limit'
    if not working_window(person['preferences'], start, end, mode): return 'outside_hours'
    if overlaps(start, end, person.get('holidays', [])): return 'holiday'
    if overlaps(start, end, person['busy']): return 'busy'
    if mode == 'In person':
        travel = travel_window(person, start, end)
        if travel['unknown']: return 'unknown'
        if travel['conflict']: return 'travel_conflict'
        depart = start - timedelta(minutes=travel['before'] + person['buffer'])
        if not working_window(person['preferences'], depart, end, mode): return 'travel_conflict'
        if overlaps(depart, start, person['busy']): return 'travel_conflict'
    return 'free'


def travel_window(person, start, end):
    before = person.get('travel_minutes')
    after = 0
    previous = [e for e in person.get('journeys', []) if e['end'] <= start and e['end'].astimezone(ZoneInfo(person['preferences']['timezone'])).date() == start.astimezone(ZoneInfo(person['preferences']['timezone'])).date()]
    following = [e for e in person.get('journeys', []) if e['start'] >= end and e['start'].astimezone(ZoneInfo(person['preferences']['timezone'])).date() == end.astimezone(ZoneInfo(person['preferences']['timezone'])).date()]
    prev = max(previous, key=lambda e:e['end'], default=None)
    nxt = min(following, key=lambda e:e['start'], default=None)
    if prev is not None: before = prev.get('from_minutes')
    if nxt is not None: after = nxt.get('to_minutes')
    unknown = before is None or after is None or bool(person.get('journey_error'))
    conflict = False
    if not unknown:
        depart = start - timedelta(minutes=before + person['buffer'])
        arrival = end + timedelta(minutes=after + (person['buffer'] if after else 0))
        conflict = bool(prev and depart < prev['end']) or bool(nxt and arrival > nxt['start'])
        if after and (overlaps(end, arrival, person['busy']) or not working_window(person['preferences'], end, arrival, 'In person')): conflict = True
    return {'before':before, 'after':after, 'unknown':unknown, 'conflict':conflict}


def build_slots(people, start, end, duration, mode, zone, exclude_before=None):
    step = timedelta(minutes=15)
    first = start.replace(second=0, microsecond=0)
    if first < start: first += timedelta(minutes=1)
    offset = first.minute % 15
    if offset: first += timedelta(minutes=15-offset)
    slots = []
    while first + timedelta(minutes=duration) <= end:
        finish = first + timedelta(minutes=duration)
        if exclude_before is None or first >= exclude_before:
            cells = [{'user':p['user'], 'status': candidate_status(p,first,finish,mode), 'required':p['required']} for p in people]
            available = all(c['status']=='free' for c in cells if c['required']) and not any(c['status']=='daily_limit' for c in cells)
            slots.append({'start':first.astimezone(ZoneInfo(zone)).isoformat(),
                          'end':finish.astimezone(ZoneInfo(zone)).isoformat(),
                          'available':available, 'people':cells,
                          'optional_conflicts':sum(c['status']!='free' for c in cells if not c['required'])})
        first += step
    return slots
