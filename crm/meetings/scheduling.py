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
    calendar_for_user(name)
    from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
    return get_google_calendar_object(name)


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
    result={'calendars':calendars,'meeting':None,'event':None,'places_browser_key':frappe.db.get_single_value('Google Settings','custom_marloa_places_browser_key')}
    if meeting:
        doc=frappe.get_doc('Marloa Meeting',meeting);doc.check_permission('write')
        if doc.crm_deal!=deal:frappe.throw('Meeting belongs to another deal.')
        result['meeting']={f:doc.get(f) for f in ('name','title','meeting_at','ends_at','mode','location_or_link','attendees','agenda')}
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
            if completed.invitation_state=='Sent':return {'name':meeting,'sent':True}
    doc=frappe.get_doc('Marloa Meeting',meeting) if meeting else frappe.new_doc('Marloa Meeting')
    if meeting:
        doc.check_permission('write')
        if doc.status=='Cancelled':frappe.throw('Create a new meeting instead of editing a cancelled invitation.')
        if doc.crm_deal!=deal:frappe.throw('Meeting belongs to another deal.')
    name=data.get('calendar')
    service,account=service_for(name)
    old_calendar,event_id=event_reference(doc)
    if old_calendar and old_calendar!=name:frappe.throw('Keep the original organizer calendar.')
    current={}
    if event_id:
        current=get_current_event(service,account.google_calendar_id,event_id,doc.invitation_state=='Needs review') or {}
        if current and (not etag or etag!=current.get('etag')):
            frappe.throw('The Google event changed. Reopen it before saving.')
    try:body=build_payload(data,current)
    except (ValueError,KeyError,TypeError) as error:frappe.throw(str(error))
    if meeting is None:
        doc.update({'title':body['summary'],'crm_deal':deal,'meeting_at':local_datetime(body['start'].get('dateTime') or body['start'].get('date')),
                    'ends_at':local_datetime(body['end'].get('dateTime') or body['end'].get('date')),
                    'mode':data.get('mode') or 'Online','status':'Scheduled','meeting_owner':frappe.session.user,
                    'location_or_link':body['location'] or 'Google Meet link pending','source_kind':'None',
                    'custom_google_request_key':request_key,'invitation_state':'Draft'})
        doc.insert()
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
    return finish(doc,event)


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
    return {'cancelled':True}
