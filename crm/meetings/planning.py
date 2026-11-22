"""Permission-scoped free/busy and travel estimates. Never return private origins."""
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import frappe
from frappe.rate_limiter import rate_limit
from crm.meetings.contacts import require_crm
from crm.meetings.preferences import read_preferences
from crm.meetings.availability_rules import aware, build_slots, candidate_status, travel_window


def own_service():
    name=frappe.db.get_value('Google Calendar',{'user':frappe.session.user,'enable':1,'push_to_google_calendar':1},'name')
    if not name:frappe.throw('Connect your own Google Calendar before checking availability.')
    from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
    return get_google_calendar_object(name)


def parse_request(data):
    if isinstance(data,str):data=json.loads(data)
    if not isinstance(data,dict):raise ValueError('Invalid scheduling details.')
    zone=str(data.get('timezone') or 'Asia/Kolkata');ZoneInfo(zone)
    start,end=aware(data['from'],zone),aware(data['to'],zone)
    duration=int(data.get('duration') or 30)
    if end<=start or end-start>timedelta(days=7,hours=1) or not 15<=duration<=480:
        raise ValueError('Choose up to seven days and a duration between 15 minutes and eight hours.')
    if start<datetime.now(timezone.utc)-timedelta(days=7):raise ValueError('Choose a current or future meeting date.')
    mode=data.get('mode')
    if mode not in ('Online','In person'):raise ValueError('Choose a meeting type.')
    location=str(data.get('location') or '').strip()
    if len(location)>500 or (mode=='In person' and not location):raise ValueError('Choose the meeting location first.')
    rows=data.get('attendees',[])
    if not isinstance(rows,list) or not 1<=len(rows)<=10:raise ValueError('Choose between one and ten internal attendees.')
    seen=set();clean=[]
    for row in rows:
        user=str(row.get('user') or '')
        if user in seen:raise ValueError('An employee is selected twice.')
        seen.add(user)
        if not frappe.db.exists('User',{'name':user,'enabled':1,'user_type':'System User'}) or not set(frappe.get_roles(user)) & {'Sales User','Sales Manager','System Manager'}:
            raise ValueError('Select active CRM employees as internal attendees.')
        clean.append({**row,'user':user,'required':bool(row.get('required',True))})
    if not any(r['required'] for r in clean):raise ValueError('Choose at least one required internal attendee.')
    return data,zone,start,end,duration,mode,location,clean


def origin_for(row, preferences):
    source=row.get('origin_source','default')
    if source not in ('manual','shared','personal','default'):return ''
    if source=='manual':return str(row.get('origin_address') or '').strip()[:500]
    if source=='shared':
        return frappe.db.get_value('CRM Meeting Place',{'name':row.get('origin_id'),'enabled':1},'address') or ''
    if source=='personal' and row['user']!=frappe.session.user:return ''
    if source=='default' and row['user']!=frappe.session.user and not preferences['share_travel_estimate']:return ''
    identity=row.get('origin_id') if source=='personal' else preferences['default_place']
    return next((p['address'] for p in preferences['places'] if p['id']==identity),'')


def route_point(value):
    import re
    match = re.fullmatch(r'\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*', value)
    if match:
        lat, lng = map(float, match.groups())
        if not -90<=lat<=90 or not -180<=lng<=180: frappe.throw('Invalid map coordinates.')
        return {'location':{'latLng':{'latitude':lat,'longitude':lng}}}
    return {'address':value}


def calendar_events(service, identity, start, end):
    events=[];page=None
    for _ in range(20):
        response=service.events().list(calendarId=identity,timeMin=start.isoformat(),timeMax=end.isoformat(),
            singleEvents=True,maxResults=250,pageToken=page,
            fields='items(id,iCalUID,start,end,status,transparency,location,conferenceData,hangoutLink,attendees(email,responseStatus,self)),nextPageToken').execute()
        events.extend(response.get('items',[]))
        page=response.get('nextPageToken')
        if not page:return events
    raise ValueError('Calendar has too many events to check safely.')


def enrich_constraints(service, person, start, end, destination, mode, excluded_uid=None, budget=None, excluded_start=None):
    prefs=person['preferences'];person['holidays']=[];person['journeys']=[]
    def interval(event):
        a=event.get('start',{});b=event.get('end',{})
        return aware(a.get('dateTime') or a['date'], a.get('timeZone') or prefs['timezone']), aware(b.get('dateTime') or b['date'], b.get('timeZone') or prefs['timezone'])
    for identity in prefs.get('holiday_calendar_ids',[]):
        try:
            for event in calendar_events(service,identity,start-timedelta(days=1),end+timedelta(days=1)):
                if event.get('status')!='cancelled':person['holidays'].append(interval(event))
        except Exception:person['calendar_error']='A selected holiday calendar could not be checked.'
    if mode!='In person':return
    try:
        seen=set();route_cache={}
        for identity in person['ids']:
            for event in calendar_events(service,identity,start-timedelta(days=1),end+timedelta(days=1)):
                if event.get('status')=='cancelled' or event.get('transparency')=='transparent':continue
                if any(a.get('self') and a.get('responseStatus')=='declined' for a in event.get('attendees',[])):continue
                a,b=interval(event)
                if excluded_uid and event.get('iCalUID')==excluded_uid and excluded_start is not None and a==excluded_start:continue
                key=(event.get('iCalUID') or event.get('id'),a.isoformat())
                if key in seen:continue
                seen.add(key)
                location=event.get('location','').strip()
                online=bool(event.get('conferenceData') or event.get('hangoutLink'))
                # A calendar event without a disclosed location cannot prove a feasible journey.
                origin=(location if location else '') if not online else person.get('origin','')
                def route(x,y,when):
                    if not x or not y:return None
                    if x==y:return 0
                    k=(x,y,when.date().isoformat())
                    if k not in route_cache:
                        if budget is not None and budget['remaining']<=0:return None
                        if budget is not None:budget['remaining']-=1
                        person['routes_used']=True
                        route_cache[k]=route_minutes(x,y,person['travel_mode'],max(datetime.now(timezone.utc),when))[0]
                    return route_cache[k]
                person['journeys'].append({'start':a,'end':b,'from_minutes':route(origin,destination,b), 'to_minutes':route(destination,origin,a)})
    except Exception:person['journey_error']=True


def route_minutes(origin, destination, mode, departure):
    key=frappe.get_single('Google Settings').get_password('custom_marloa_routes_server_key',raise_exception=False)
    if not key:return None,'Routes API key is not configured. Enter a manual travel estimate.'
    body={'origin':route_point(origin),'destination':route_point(destination),'travelMode':mode}
    if mode in ('DRIVE','TWO_WHEELER'):
        body['routingPreference']='TRAFFIC_AWARE'
    if mode in ('DRIVE','TRANSIT','TWO_WHEELER') and departure>datetime.now(timezone.utc):
        body['departureTime']=departure.isoformat()
    cache_body={**body}
    if 'departureTime' in cache_body:
        cache_body['departureTime']=departure.replace(minute=(departure.minute//15)*15,second=0,microsecond=0).isoformat()
    cache_key='meeting-route:'+hashlib.sha256(json.dumps(cache_body,sort_keys=True).encode()).hexdigest()
    cached=frappe.cache.get_value(cache_key)
    if cached is not None:return cached,None
    import requests
    try:
        response=requests.post('https://routes.googleapis.com/directions/v2:computeRoutes',json=body,
            headers={'X-Goog-Api-Key':key,'X-Goog-FieldMask':'routes.duration'},timeout=12)
        if response.status_code in (401,403):return None,'Google Routes access is unavailable. Check the server key and API enablement.'
        response.raise_for_status()
        routes=response.json().get('routes',[])
        if not routes:return None,'No route found. Enter a manual travel estimate.'
        seconds=float(routes[0]['duration'].rstrip('s'))
        minutes=math.ceil(seconds/60)
        frappe.cache.set_value(cache_key,minutes,expires_in_sec=300)
        return minutes,None
    except Exception:
        return None,'Travel estimate unavailable. Enter a manual estimate or retry.'


def representative_departure(preferences,start,end):
    zone=ZoneInfo(preferences['timezone'])
    day=start.astimezone(zone).date()
    while day<=end.astimezone(zone).date():
        intervals=preferences['weekly']['In person'][day.weekday()]
        for override in preferences['exceptions']:
            if override['date']==day.isoformat() and override['mode']=='In person':
                intervals=override['windows'];break
        for a,b in intervals:
            candidate=aware(day.isoformat()+'T'+a,preferences['timezone'])
            if candidate>=start and candidate<end:return candidate
        day+=timedelta(days=1)
    return start


def visit_counts(user, preferences, start, end, exclude=None):
    # CRM records only: do not infer physical attendance from private Google titles.
    system_zone = frappe.utils.get_system_timezone()
    rows = frappe.get_all('Marloa Meeting', filters={
        'mode': 'In person', 'status': ['!=', 'Cancelled'],
        'meeting_at': ['between', [
            (start-timedelta(days=2)).astimezone(ZoneInfo(system_zone)).replace(tzinfo=None),
            (end+timedelta(days=2)).astimezone(ZoneInfo(system_zone)).replace(tzinfo=None)]]},
        fields=['name', 'meeting_at', 'meeting_owner', 'custom_marloa_scheduling_summary', 'custom_google_guest_responses'])
    counts = {}
    email = frappe.db.get_value('User', user, 'email') or user
    for row in rows:
        if row.name == exclude: continue
        responses = json.loads(row.custom_google_guest_responses or '[]')
        if any(a.get('email', '').lower() == email.lower() and a.get('responseStatus') == 'declined' for a in responses): continue
        attendees = json.loads(row.custom_marloa_scheduling_summary or '[]')
        if not any(a.get('user') == user for a in attendees) and row.meeting_owner != user: continue
        day = aware(row.meeting_at, system_zone).astimezone(ZoneInfo(preferences['timezone'])).date().isoformat()
        counts[day] = counts.get(day, 0) + 1
    return counts


def plan(deal, data, selected_time=False, meeting=None):
    require_crm();frappe.get_doc('CRM Deal',deal).check_permission('read')
    try:data,zone,start,end,duration,mode,location,rows=parse_request(data)
    except (ValueError,TypeError,KeyError) as error:frappe.throw(str(error))
    service,account=own_service()
    people=[];calendar_ids=set();route_budget={'remaining':24}
    for row in rows:
        preferences,_=read_preferences(row['user'])
        email=frappe.db.get_value('User',row['user'],'email') or row['user']
        ids=list(dict.fromkeys([email]+preferences.get('calendar_ids',[])))
        calendar_ids.update(ids)
        person={'user':row['user'],'name':frappe.db.get_value('User',row['user'],'full_name'),
                'required':row['required'],'preferences':preferences,'ids':ids,'busy':[],
                'calendar_error':None,'travel_minutes':0,'buffer':0,'travel_status':'not_needed'}
        if mode=='In person':
            person['origin']=origin_for(row,preferences)
            person['travel_mode']=row.get('travel_mode') or preferences['travel_mode']
            person['buffer']=int(row.get('buffer_minutes',preferences['buffer_minutes']))
            if not 0<=person['buffer']<=180:frappe.throw('Arrival buffer must be between zero and 180 minutes.')
            manual=row.get('manual_minutes')
            if manual is not None and manual!='':
                person['travel_minutes']=int(manual)
                if not 0<=person['travel_minutes']<=1440:frappe.throw('Manual travel time must be between zero and 1440 minutes.')
                person['travel_status']='manual'
            else:
                origin=origin_for(row,preferences)
                travel_mode=row.get('travel_mode') or preferences['travel_mode']
                if travel_mode not in ('DRIVE','WALK','TRANSIT','BICYCLE','TWO_WHEELER'):frappe.throw('Invalid travel mode.')
                if origin:
                    # Estimate near the proposed departure; recheck for the selected slot before sending.
                    depart=max(datetime.now(timezone.utc),representative_departure(preferences,start,end))
                    person['routes_used']=True
                    person['travel_minutes'],warning=route_minutes(origin,location,travel_mode,depart)
                    if selected_time and person['travel_minutes'] is not None:
                        refined=max(datetime.now(timezone.utc),start-timedelta(minutes=person['buffer']+person['travel_minutes']))
                        person['routes_used']=True
                        person['travel_minutes'],warning=route_minutes(origin,location,travel_mode,refined)
                    person['travel_status']=warning or 'estimated'
                else:
                    person['travel_minutes']=None
                    person['travel_status']='Choose a departure place or enter a manual estimate.'
        if mode == 'In person' and preferences.get('max_in_person_per_day') is not None:
            person['daily_counts'] = visit_counts(row['user'], preferences, start, end, meeting)
        people.append(person)
    if len(calendar_ids)>50:frappe.throw('Too many calendars selected. Reduce the attendee calendar choices.')
    # Include the travel window before the first candidate. Free/busy never exposes event titles.
    try:
        response=service.freebusy().query(body={'timeMin':(start-timedelta(days=2)).isoformat(),
            'timeMax':end.isoformat(),'timeZone':zone,'items':[{'id':x} for x in sorted(calendar_ids)]}).execute()
        calendar_data=response.get('calendars',{})
    except Exception:
        calendar_data={}
    for person in people:
        for identity in person['ids']:
            entry=calendar_data.get(identity)
            if entry is None or entry.get('errors'):
                person['calendar_error']='Calendar sharing or Google authorization is unavailable.';continue
            person['busy'] += [(aware(v['start'],'UTC'),aware(v['end'],'UTC')) for v in entry.get('busy',[])]
    if meeting:
        doc=frappe.get_doc('Marloa Meeting',meeting);doc.check_permission('read')
        if doc.crm_deal!=deal:frappe.throw('Meeting belongs to another deal.')
        from crm.meetings.scheduling import event_reference,service_for,get_current_event
        name,event_id=event_reference(doc)
        if name and event_id:
            event_service,event_account=service_for(name)
            current=get_current_event(event_service,event_account.google_calendar_id,event_id)
            uid=current.get('iCalUID')
            original=current.get('start',{})
            for person in people:
                periods=[]
                try:
                    for identity in person['ids']:
                        page=None
                        while True:
                            response=service.events().list(calendarId=identity,timeMin=(start-timedelta(days=2)).isoformat(),timeMax=end.isoformat(),singleEvents=True,maxResults=250,pageToken=page,fields='items(id,iCalUID,start,end,status,transparency),nextPageToken').execute()
                            for event in response.get('items',[]):
                                if event.get('status')=='cancelled' or event.get('transparency')=='transparent':continue
                                same_uid=bool(uid and event.get('iCalUID')==uid)
                                event_start=event.get('start',{})
                                same_start=event_start==original
                                if event_start.get('dateTime') and original.get('dateTime'):
                                    same_start=aware(event_start['dateTime'],zone)==aware(original['dateTime'],zone)
                                if same_uid and same_start:continue
                                a=event_start.get('dateTime') or event_start.get('date')
                                b=event.get('end',{}).get('dateTime') or event.get('end',{}).get('date')
                                if a and b:periods.append((aware(a,zone),aware(b,zone)))
                            page=response.get('nextPageToken')
                            if not page:break
                    person['busy']=periods
                    person['calendar_error']=None
                except Exception:
                    person['calendar_error']='Unable to check other commitments while editing. Calendar read access is required.'

    excluded_uid = current.get('iCalUID') if meeting and name and event_id else None
    excluded_start = aware(current['start'].get('dateTime') or current['start']['date'],zone) if excluded_uid else None
    for person in people:
        enrich_constraints(service,person,start,end,location,mode,excluded_uid,route_budget,excluded_start)
    slots=build_slots(people,start,end,duration,mode,zone,datetime.now(timezone.utc))
    if selected_time:
        cells=[{'user':p['user'],'status':candidate_status(p,start,end,mode),'required':p['required']} for p in people]
        slots=[{'start':start.isoformat(),'end':end.isoformat(),'people':cells,
                'available':all(c['status']=='free' for c in cells if c['required']) and not any(c['status']=='daily_limit' for c in cells)}]
    suggestions=sorted([s for s in slots if s['available']],key=lambda s:(s.get('optional_conflicts',0),s['start']))[:12]
    summaries=[{'user':p['user'],'name':p['name'],'required':p['required'],'configured':p['preferences']['configured'],
        'calendar_error':p['calendar_error'],'travel_minutes':p['travel_minutes'],'buffer_minutes':p['buffer'],
        'travel_status':p['travel_status'], 'journey_error':bool(p.get('journey_error')),  'daily_limit':p['preferences'].get('max_in_person_per_day'),
        'daily_counts':p.get('daily_counts', {}), 'timezone':p['preferences']['timezone']} for p in people]
    for slot in slots:
        if mode=='In person':
            a,b=aware(slot['start'],zone),aware(slot['end'],zone)
            slot['travel']=[{'user':p['user'],**travel_window(p,a,b),'buffer':p['buffer']} for p in people]
    return {'people':summaries,'slots':slots,'suggestions':suggestions,'timezone':zone,
            'services':{'routes':('error' if any(p.get('routes_used') and (p['travel_minutes'] is None or p.get('journey_error')) for p in people) else 'connected') if any(p.get('routes_used') for p in people) else 'unused'},
            'checked_at':datetime.now(timezone.utc).isoformat(),'travel_estimate':mode=='In person',
            'external_availability':'External guests are not checked unless their calendars are explicitly shared.'}


@frappe.whitelist()
@rate_limit(limit=10, seconds=60, user_based=True)
def find_times(deal, data, meeting=None):
    return plan(deal,data,meeting=meeting)


def check_before_send(deal,data,meeting=None):
    if data.get('all_day') or data.get('repeat','NONE')!='NONE':
        # One availability check cannot validate every recurrence or all-day travel.
        if not data.get('availability_override_reason'):
            frappe.throw('For all-day or recurring invitations, add an explicit availability override reason. Only managers can approve this.')
    internal=data.get('internal_attendees')
    if not internal:frappe.throw('Choose internal attendees before sending the invitation.')
    # Serialize CRM bookings for the same employees until the invitation transaction commits.
    for user in sorted({r['user'] for r in internal}):
        frappe.db.sql('select name from `tabUser` where name=%s for update', (user,))
    end=data['end']
    if data.get('all_day'):
        from datetime import date
        end=(date.fromisoformat(str(end)[:10])+timedelta(days=1)).isoformat()
    request={'from':data['start'],'to':end,'duration':30,'timezone':data.get('timezone'),
        'mode':data.get('mode'),'location':data.get('location'),'attendees':internal}
    result=plan(deal,request,selected_time=True,meeting=meeting)
    issues=[c for c in result['slots'][0]['people'] if (c['required'] and c['status']!='free') or c['status']=='daily_limit']
    reason=str(data.get('availability_override_reason') or '').strip()
    if issues or data.get('all_day') or data.get('repeat','NONE')!='NONE':
        from crm.meetings.permissions import is_manager
        if not is_manager() or len(reason)<8:
            labels={'busy':'already busy','outside_hours':'outside working hours','holiday':'observed holiday','daily_limit':'daily in-person meeting limit reached','travel_conflict':'not enough travel time','unknown':'calendar, working hours or travel details are unavailable'}
            names={p['user']:p.get('name') or p['user'] for p in result.get('people',[])}
            details='; '.join(names.get(c['user'],c['user'])+': '+labels.get(c['status'],c['status']) for c in issues)
            frappe.throw('Meeting not sent. '+(details+'. ' if details else '')+'Choose another time, or ask a manager to provide an override reason of at least eight characters.')
    return result,reason


@frappe.whitelist()
@rate_limit(limit=3, seconds=60, user_based=True)
def test_routes_connection():
    require_crm()
    frappe.only_for('System Manager')
    key=frappe.get_single('Google Settings').get_password('custom_marloa_routes_server_key',raise_exception=False)
    if not key:return {'configured':False,'working':False,'message':'Enter a Routes API server key in Google Settings.'}
    minutes,warning=route_minutes('Ernakulam Junction, Kochi, Kerala, India','Infopark, Kochi, Kerala, India','DRIVE',datetime.now(timezone.utc)+timedelta(hours=1))
    return {'configured':True,'working':minutes is not None,'message':warning or 'Google Routes API responded successfully.'}
