"""Meeting workspace APIs. Every request is scoped to an accessible deal."""
import frappe


@frappe.whitelist()
def list_meetings(deal):
    frappe.get_doc('CRM Deal', deal).check_permission('read')
    fields = ['name', 'title', 'meeting_at', 'ends_at', 'mode', 'status',
              'meeting_owner', 'location_or_link', 'attendees', 'agenda',
              'summary', 'decisions', 'next_actions', 'calendar_event', 'invitation_state', 'custom_google_event_id', 'custom_google_guest_responses', 'custom_google_options']
    meta = frappe.get_meta('Marloa Meeting')
    fields = [f for f in fields if f == 'name' or meta.has_field(f)]
    meetings = frappe.get_list('Marloa Meeting', filters={'crm_deal': deal},
                           fields=fields, order_by='meeting_at desc', limit_page_length=500)

    from frappe.utils import get_datetime, now_datetime
    import json
    from collections import Counter
    series_ids = set()
    for meeting in meetings:
        options = json.loads(meeting.pop('custom_google_options', None) or '{}')
        if options.get('recurringEventId'):
            series_ids.add(options['recurringEventId'])
    meetings = [m for m in meetings if m.get('custom_google_event_id') not in series_ids]
    from crm.meetings.permissions import is_manager
    manager=is_manager()
    for meeting in meetings:
        doc=frappe.get_doc('Marloa Meeting',meeting.name)
        meeting['can_edit_notes']=doc.has_permission('write')
        meeting['can_edit_invitation']=meeting['can_edit_notes'] and (manager or meeting.meeting_owner==frappe.session.user)
        responses = json.loads(meeting.get("custom_google_guest_responses") or "[]")
        counts = Counter(a.get("responseStatus", "needsAction") for a in responses if not a.get("organizer"))
        labels = {"accepted":"accepted", "declined":"declined", "tentative":"tentative", "needsAction":"awaiting response"}
        meeting["response_summary"] = " · ".join(str(n) + " " + labels.get(status,status) for status,n in counts.items())
        end = meeting.get("ends_at") or meeting.get("meeting_at")
        meeting["is_past"] = bool(end and get_datetime(end) < now_datetime())
    return meetings


@frappe.whitelist()
def meetings_to_link():
    return frappe.get_list('CRM Calendar Inbox', filters={
        'owner':frappe.session.user,'state':'Needs linking'},
        fields=['name','title','starts_at'],order_by='starts_at desc',limit_page_length=100)


@frappe.whitelist()
def link_calendar_meeting(name, deal=None, ignore=False):
    from crm.meetings.google_sync import upsert_event
    import json
    inbox=frappe.get_doc('CRM Calendar Inbox',name)
    inbox.check_permission('write')
    if inbox.owner != frappe.session.user:
        frappe.throw('This meeting belongs to another employee.',frappe.PermissionError)
    if frappe.utils.cint(ignore):
        inbox.state='Ignored';inbox.save();return
    if not deal:
        frappe.throw('Choose a deal.')
    frappe.get_doc('CRM Deal',deal).check_permission('write')
    inbox.deal=deal;inbox.etag=None;inbox.save()
    account=frappe.get_doc('Google Calendar',inbox.calendar)
    if account.user != frappe.session.user:
        frappe.throw('Calendar ownership mismatch.',frappe.PermissionError)
    upsert_event(account,json.loads(inbox.event_data))
    return {'linked':True}
