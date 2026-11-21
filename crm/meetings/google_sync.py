"""Incremental Google imports into an owner-private review queue.

Only explicitly approved customer calendars are read. Native framework pull must
remain off for these calendars, because it does not apply CRM matching rules.
"""
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_system_timezone
from crm.meetings.matching import google_event_identity, choose_deal


@contextmanager
def calendar_user(user):
    previous = frappe.session.user
    frappe.set_user(user)
    try:
        yield
    finally:
        frappe.set_user(previous)


def sync_customer_calendars():
    calendars = frappe.get_all('Google Calendar', filters={
        'enable':1,'custom_marloa_customer_calendar':1,'custom_marloa_sync_enabled':1},
        fields=['name','user'])
    for calendar in calendars:
        try:
            with calendar_user(calendar.user):
                with frappe.cache.lock('marloa-calendar-' + calendar.name, timeout=240, blocking_timeout=1):
                    sync_calendar(calendar.name)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            # No guest data or OAuth token is included in diagnostic output.
            frappe.db.set_value('Google Calendar', calendar.name, 'custom_marloa_sync_status',
                                'Sync failed; check calendar authorization and retry.')
            frappe.db.commit()


def local_datetime(value):
    if not value:
        return None
    if len(value) == 10:
        return value + ' 00:00:00'
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo:
        parsed = parsed.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)
    return parsed.strftime('%Y-%m-%d %H:%M:%S')


def sync_calendar(name):
    from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
    service, account = get_google_calendar_object(name)
    if account.user != frappe.session.user:
        frappe.throw('This calendar belongs to another employee.', frappe.PermissionError)
    if not account.custom_marloa_customer_calendar or not account.custom_marloa_sync_enabled:
        return
    if account.pull_from_google_calendar:
        frappe.throw('Disable framework calendar pull before enabling CRM customer-only import.')
    if account.google_calendar_id in ('primary', account.user):
        frappe.throw('Select a dedicated customer calendar instead of primary.')
    calendar_entry=service.calendarList().get(calendarId=account.google_calendar_id).execute()
    if calendar_entry.get('primary'):
        frappe.throw('Primary calendars cannot be imported by customer-calendar sync.')
    token = account.get_password('custom_marloa_sync_token', raise_exception=False)
    page = None
    while True:
        args = {'calendarId':account.google_calendar_id, 'maxResults':250,
                'singleEvents':True, 'showDeleted':True}
        if token:
            args['syncToken'] = token
        else:
            # Start with recent/future meetings, not the entire historical calendar.
            from frappe.utils import add_days, now_datetime
            args['timeMin'] = add_days(now_datetime(), -30).replace(tzinfo=ZoneInfo(get_system_timezone())).isoformat()
        if page:
            args['pageToken'] = page
        try:
            response = service.events().list(**args).execute()
        except Exception as error:
            if getattr(getattr(error,'resp',None),'status',None) == 410:
                from frappe.utils.password import set_encrypted_password
                set_encrypted_password('Google Calendar',name,'','custom_marloa_sync_token')
                return
            raise
        for event in response.get('items',[]):
            upsert_event(account, event)
        page = response.get('nextPageToken')
        if not page:
            if response.get('nextSyncToken'):
                from frappe.utils.password import set_encrypted_password
                set_encrypted_password('Google Calendar',name,response['nextSyncToken'],'custom_marloa_sync_token')
            break
    frappe.db.set_value('Google Calendar',name,'custom_marloa_sync_status','Customer calendar sync completed.')


def matching_records(emails):
    # Child-table lookups only locate candidates; parent permissions are applied below.
    names = frappe.get_all('Contact Email', filters={'email_id':['in',emails]}, pluck='parent') if emails else []
    permitted = frappe.get_list('Contact', filters={'name':['in',names]}, pluck='name',limit_page_length=0) if names else []
    contacts = []
    company_contacts = {}
    for name in permitted:
        doc = frappe.get_doc('Contact',name)
        contacts.append({'name':name,'emails':[e.email_id for e in doc.email_ids]})
        if doc.company_name:
            company_contacts.setdefault(doc.company_name,[]).append(name)
    deal_names = frappe.get_all('CRM Contacts',filters={'contact':['in',permitted],'parenttype':'CRM Deal'},pluck='parent') if permitted else []
    if company_contacts:
        deal_names += frappe.get_list('CRM Deal',filters={'organization':['in',list(company_contacts)]},pluck='name',limit_page_length=0)
    deals = frappe.get_list('CRM Deal',filters={'name':['in',deal_names]},fields=['name','status'],limit_page_length=0) if deal_names else []
    for deal in deals:
        doc=frappe.get_doc('CRM Deal',deal.name)
        deal['contacts']=[r.contact for r in doc.contacts] + company_contacts.get(doc.organization,[])
        status=frappe.db.get_value('CRM Deal Status',deal.status,'type')
        deal['closed']=status in ('Won','Lost')
    return contacts,deals


def upsert_event(account, event):
    key=hashlib.sha256(google_event_identity(account.google_calendar_id,event).encode()).hexdigest()
    existing=frappe.db.get_value('CRM Calendar Inbox',{'google_key':key},'name')
    inbox=frappe.get_doc('CRM Calendar Inbox',existing) if existing else frappe.new_doc('CRM Calendar Inbox')
    if existing and inbox.owner != frappe.session.user:
        return  # Shared calendar already managed by its original connected owner.
    if existing and inbox.etag == event.get('etag'):
        return
    inbox.google_key=key;inbox.calendar=account.name;inbox.event_id=event['id'];inbox.etag=event.get('etag')
    if not existing:
        previous=frappe.db.get_value('Marloa Meeting',{'custom_google_event_key':key},'name')
        previous=previous or frappe.db.get_value('Event',{'google_calendar_event_id':event['id'],'google_calendar':account.name},'custom_marloa_meeting')
        if previous:
            original=frappe.get_doc('Marloa Meeting',previous)
            original.check_permission('read')
            inbox.meeting=previous;inbox.deal=original.crm_deal
    if event.get('status') == 'cancelled':
        if not existing and not inbox.meeting:
            return
        inbox.title=event.get('summary') or (frappe.db.get_value('Marloa Meeting',inbox.meeting,'title') if inbox.meeting else 'Cancelled meeting')
        inbox.state='Cancelled'
        if inbox.meeting:
            meeting=frappe.get_doc('Marloa Meeting',inbox.meeting);meeting.check_permission('write')
            meeting.status='Cancelled';meeting.invitation_state='Cancelled';meeting.save()
        inbox.save();return
    if event.get('eventType','default') != 'default':
        return
    emails=[a['email'].lower() for a in event.get('attendees',[]) if a.get('email') and not a.get('self') and not a.get('resource')]
    if not emails:
        return
    inbox.title=event.get('summary') or 'Untitled meeting'
    inbox.starts_at=local_datetime(event.get('start',{}).get('dateTime') or event.get('start',{}).get('date'))
    data={k:event.get(k) for k in ('id','etag','summary','description','location','start','end','attendees','hangoutLink','conferenceData','recurrence','extendedProperties','recurringEventId','originalStartTime','reminders','visibility','transparency','attachments','guestsCanModify','guestsCanInviteOthers','guestsCanSeeOtherGuests')}
    inbox.event_data=json.dumps(data)
    if inbox.state == 'Ignored':
        inbox.save();return
    if not inbox.deal:
        contacts,deals=matching_records(emails)
        explicit=event.get('extendedProperties',{}).get('private',{}).get('marloa_deal')
        if explicit and frappe.get_list('CRM Deal',filters={'name':explicit},pluck='name'):
            if explicit not in [d['name'] for d in deals]:deals.append({'name':explicit,'contacts':[]})
        else:explicit=None
        match=choose_deal(emails,contacts,deals,explicit_deal=explicit)
        inbox.deal=match['deal']
    if inbox.deal:
        frappe.get_doc('CRM Deal',inbox.deal).check_permission('read')
        inbox.state='Linked'
        meeting=frappe.get_doc('Marloa Meeting',inbox.meeting) if inbox.meeting else frappe.new_doc('Marloa Meeting')
        if inbox.meeting:
            meeting.check_permission('write')
        meeting.update({'title':inbox.title,'crm_deal':inbox.deal,'meeting_at':inbox.starts_at,
            'ends_at':local_datetime(event.get('end',{}).get('dateTime') or event.get('end',{}).get('date')),
            'mode':'Online' if event.get('hangoutLink') or event.get('conferenceData') else 'In person',
            'meeting_owner':account.user,'location_or_link':event.get('hangoutLink') or event.get('location') or 'Location not specified',
            'attendees':', '.join(emails),'agenda':event.get('description') or '',
            'invitation_state':'Sent','custom_google_event_key':key,'custom_google_calendar':account.name,'custom_google_event_id':event['id'],'custom_google_etag':event.get('etag'),'custom_google_guest_responses':json.dumps(event.get('attendees',[])),
            'custom_google_options':json.dumps(data)})
        if not inbox.meeting:
            meeting.status='Scheduled'
        meeting.save();inbox.meeting=meeting.name
    else:
        inbox.state='Needs linking'
    inbox.save()
    if not existing and inbox.state=='Needs linking':
        frappe.get_doc({'doctype':'Notification Log','subject':'Calendar meeting needs linking',
            'for_user':account.user,'type':'Alert','document_type':'CRM Calendar Inbox','document_name':inbox.name}).insert(ignore_permissions=True)
