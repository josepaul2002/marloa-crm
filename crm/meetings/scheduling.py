"""Single-send Google scheduling with deterministic creation IDs and revision checks."""
import hashlib,json
import frappe
from crm.meetings.event_payload import build_payload
from crm.meetings.google_sync import local_datetime


def calendar_for_user(name):
    doc=frappe.get_doc('Google Calendar',name)
    if doc.user!=frappe.session.user or not doc.enable or not doc.push_to_google_calendar:
        frappe.throw('Choose your own enabled organizer calendar.',frappe.PermissionError)
    return doc


def service_for(name):
    from crm.meetings.permissions import check_calendar
    return check_calendar(name)


def get_current_event(service, calendar_id, event_id, allow_missing=False):
    try:
        return service.events().get(calendarId=calendar_id,eventId=event_id).execute()
    except Exception as error:
        if allow_missing and getattr(getattr(error,'resp',None),'status',None)==404:
            return None
        raise


@frappe.whitelist()
def scheduling_context(deal, meeting=None):
    frappe.get_doc('CRM Deal',deal).check_permission('read')
    calendars=frappe.get_list('Google Calendar',filters={'user':frappe.session.user,'enable':1,'push_to_google_calendar':1},fields=['name'],limit_page_length=100)
    from crm.meetings.permissions import is_manager
    if is_manager() and calendars:
        try:
            from crm.meetings.planning import own_service
            actor_service,_=own_service()
            writable=set();page=None
            while True:
                entries=actor_service.calendarList().list(maxResults=250,pageToken=page).execute()
                writable.update(e['id'] for e in entries.get('items',[]) if e.get('accessRole') in ('writer','owner'))
                page=entries.get('nextPageToken')
                if not page:break
            for target in frappe.get_all('Google Calendar',filters={'enable':1,'push_to_google_calendar':1},fields=['name','user','google_calendar_id']):
                identity=target.user if target.google_calendar_id=='primary' else target.google_calendar_id
                if target.user!=frappe.session.user and identity in writable and target.name not in [c.name for c in calendars]:
                    calendars.append(frappe._dict(name=target.name))
        except Exception:
            pass  # Existing owner calendars remain available; access is rechecked on send.
    if meeting:
        target=frappe.get_doc('Marloa Meeting',meeting)
        target.check_permission('read')
        target_calendar,_=event_reference(target)
        if is_manager() and target_calendar and target_calendar not in [c.name for c in calendars]:
            calendars.append(frappe._dict(name=target_calendar))
    from crm.meetings.preferences import read_preferences
    preferences,_=read_preferences(frappe.session.user)
    result={'timezone':preferences['timezone'],'can_override':is_manager(),'calendars':calendars,'meeting':None,'event':None,'places_browser_key':frappe.db.get_single_value('Google Settings','custom_marloa_places_browser_key')}
    if meeting:
        doc=frappe.get_doc('Marloa Meeting',meeting);doc.check_permission('write')
        if doc.crm_deal!=deal:frappe.throw('Meeting belongs to another deal.')
        result['meeting']={f:doc.get(f) for f in ('name','title','meeting_at','ends_at','mode','location_or_link','attendees','agenda')}
        result['internal_attendees']=json.loads(doc.get('custom_marloa_scheduling_summary') or '[]')
        name,event_id=event_reference(doc)
        if name and event_id:
            service,account=service_for(name)
            result['event']=get_current_event(service,account.google_calendar_id,event_id,doc.invitation_state=='Needs review')
            result['calendar']=name
    return result


def event_reference(doc):
    if doc.custom_google_calendar and doc.custom_google_event_id:
        return doc.custom_google_calendar,doc.custom_google_event_id
    if doc.calendar_event:
        event=frappe.get_doc('Event',doc.calendar_event)
        return event.google_calendar,event.google_calendar_event_id
    return None,None


@frappe.whitelist()
def save_invitation(deal, data, request_id, meeting=None, etag=None):
    frappe.get_doc('CRM Deal',deal).check_permission('write')
    if isinstance(data,str):data=json.loads(data)
    if not isinstance(data,dict) or not isinstance(request_id,str) or not 8<=len(request_id)<=100:
        frappe.throw('Invalid scheduling request.')
    with frappe.cache.lock('meeting-save-'+frappe.session.user+'-'+request_id,timeout=90,blocking_timeout=1):
        return _save_invitation(deal,data,request_id,meeting,etag)


def _save_invitation(deal,data,request_id,meeting,etag):
    request_key=hashlib.sha256((frappe.session.user+':'+request_id).encode()).hexdigest()
    if not meeting:
        meeting=frappe.db.get_value('Marloa Meeting',{'custom_google_request_key':request_key},'name')
        if meeting:
            completed=frappe.get_doc('Marloa Meeting',meeting)
            completed.check_permission('write')
            if completed.crm_deal!=deal:frappe.throw('Meeting belongs to another deal.')
            if completed.invitation_state=='Sent':return {'name':meeting,'sent':True}
    doc=frappe.get_doc('Marloa Meeting',meeting) if meeting else frappe.new_doc('Marloa Meeting')
    if meeting:
        doc.check_permission('write')
        if doc.status=='Cancelled':frappe.throw('Create a new meeting instead of editing a cancelled invitation.')
        if doc.crm_deal!=deal:frappe.throw('Meeting belongs to another deal.')
    from crm.meetings.planning import check_before_send
    availability,override_reason=check_before_send(deal,data,meeting)
    from crm.meetings.event_payload import emails
    required=emails(data.get('invitees')); optional=emails(data.get('optional_invitees'))
    for row in data['internal_attendees']:
        email=frappe.db.get_value('User',row['user'],'email') or row['user']
        (required if row.get('required',True) else optional).append(email)
    data['invitees']=required;data['optional_invitees']=optional
    name=data.get('calendar')
    service,account=service_for(name)
    old_calendar,event_id=event_reference(doc)
    if old_calendar and old_calendar!=name:frappe.throw('Keep the original organizer calendar.')
    current={}
    if event_id:
        current=get_current_event(service,account.google_calendar_id,event_id,doc.invitation_state=='Needs review') or {}
        if current.get('status')=='cancelled':frappe.throw('This Google invitation was cancelled. Create a new meeting.')
        if current and (not etag or etag!=current.get('etag')):
            frappe.throw('The Google event changed. Reopen it before saving.')
    try:body=build_payload(data,current)
    except (ValueError,KeyError,TypeError) as error:frappe.throw(str(error))
    if meeting is None:
        doc.update({'title':body['summary'],'crm_deal':deal,'meeting_at':local_datetime(body['start'].get('dateTime') or body['start'].get('date')),
                    'ends_at':local_datetime(body['end'].get('dateTime') or body['end'].get('date')),
                    'mode':data.get('mode') or 'Online','status':'Scheduled','meeting_owner':account.user,
                    'location_or_link':body['location'] or 'Google Meet link pending','source_kind':'None',
                    'custom_google_request_key':request_key,'invitation_state':'Draft'})
        doc.insert()
    doc.meeting_at=local_datetime(body['start'].get('dateTime') or body['start'].get('date'))
    doc.ends_at=local_datetime(body['end'].get('dateTime') or body['end'].get('date'))
    doc.mode=data.get('mode') or 'Online'
    doc.custom_marloa_scheduling_summary=json.dumps([{k:r.get(k) for k in ('user','required','travel_mode','buffer_minutes')} for r in data['internal_attendees']])
    doc.custom_google_calendar=name
    if not event_id:event_id=hashlib.sha256(('marloa-meeting:'+doc.name).encode()).hexdigest()
    doc.custom_google_event_id=event_id
    if doc.invitation_state=='Needs review' and not current:
        # A prior insert might have succeeded even if its response was lost.
        try:
            recovered=service.events().get(calendarId=account.google_calendar_id,eventId=event_id).execute()
        except Exception as error:
            if getattr(getattr(error,'resp',None),'status',None)!=404:raise
        else:
            return finish(doc,recovered)
    body['extendedProperties']={'private':{**current.get('extendedProperties',{}).get('private',{}),'marloa_deal':deal,'marloa_meeting':doc.name}}
    if data.get('mode')=='Online':
        if not current.get('conferenceData'):
            body['conferenceData']={'createRequest':{'requestId':request_key,'conferenceSolutionKey':{'type':'hangoutsMeet'}}}
    else:body['conferenceData']=None
    doc.invitation_state='Needs review';doc.save()
    # Persist the recovery identity before making an external request.
    frappe.db.commit()
    try:
        if current:
            request=service.events().patch(calendarId=account.google_calendar_id,eventId=event_id,body=body,
                                          conferenceDataVersion=1,supportsAttachments=True,sendUpdates='all')
            request.headers['If-Match']=etag
        else:
            body['id']=event_id
            request=service.events().insert(calendarId=account.google_calendar_id,body=body,
                                           conferenceDataVersion=1,supportsAttachments=True,sendUpdates='all')
        event=request.execute()
    except Exception:
        frappe.throw('Google did not confirm the result. Reopen this meeting to check its status before retrying.')
    result=finish(doc,event)
    from frappe.utils import escape_html
    doc.add_comment('Info', 'Invitation saved by '+escape_html(frappe.session.user)+('. Availability override: '+escape_html(override_reason) if override_reason else '. Availability checked.'))
    return result


def finish(doc,event):
    calendar_id=frappe.db.get_value('Google Calendar',doc.custom_google_calendar,'google_calendar_id')
    key=hashlib.sha256((calendar_id+':'+event['id']).encode()).hexdigest()
    doc.update({'custom_google_event_key':key,'title':event.get('summary') or doc.title,'meeting_at':local_datetime(event['start'].get('dateTime') or event['start'].get('date')),
                'ends_at':local_datetime(event['end'].get('dateTime') or event['end'].get('date')),
                'mode':'Online' if event.get('conferenceData') or event.get('hangoutLink') else 'In person',
                'location_or_link':event.get('hangoutLink') or event.get('location') or 'Google Meet link processing',
                'agenda':event.get('description') or '',
                'attendees':', '.join(a['email'] for a in event.get('attendees',[]) if a.get('email')),
                'invitation_state':'Sent','custom_google_etag':event.get('etag'),
                'custom_google_options':json.dumps(event),'custom_google_guest_responses':json.dumps(event.get('attendees',[]))})
    if doc.calendar_event:
        # This event is now managed by this integration; prevent a second native send.
        frappe.db.set_value('Event',doc.calendar_event,'sync_with_google_calendar',0)
    doc.save()
    return {'name':doc.name,'sent':True}


@frappe.whitelist()
def cancel_invitation(deal,meeting,etag):
    frappe.get_doc('CRM Deal',deal).check_permission('write')
    doc=frappe.get_doc('Marloa Meeting',meeting);doc.check_permission('write')
    if doc.crm_deal!=deal:frappe.throw('Meeting belongs to another deal.')
    name,event_id=event_reference(doc)
    if not name or not event_id:frappe.throw('No Google invitation is linked.')
    if not etag:frappe.throw('Reopen the event before cancelling.')
    service,account=service_for(name)
    request=service.events().patch(calendarId=account.google_calendar_id,eventId=event_id,
                                   body={'status':'cancelled'},sendUpdates='all')
    request.headers['If-Match']=etag
    request.execute()
    doc.status='Cancelled';doc.invitation_state='Cancelled';doc.save()
    from frappe.utils import escape_html
    doc.add_comment('Info','Google invitation cancelled by '+escape_html(frappe.session.user))
    return {'cancelled':True}
