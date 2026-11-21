"""Deal access controls CRM data; Google write access controls invitation changes."""
import json
import frappe


def is_manager(user=None):
    return bool(set(frappe.get_roles(user or frappe.session.user)) & {'System Manager', 'Sales Manager'})


def meeting_has_permission(doc, ptype=None, user=None, **kwargs):
    user = user or frappe.session.user
    if not doc.get('crm_deal'): return None
    if not frappe.has_permission('CRM Deal', 'read', doc.crm_deal, user=user): return False
    if ptype in ('write', 'create', 'delete', 'cancel', 'submit'):
        if not frappe.has_permission('CRM Deal', 'write', doc.crm_deal, user=user): return False
        assigned = json.loads(frappe.db.get_value('CRM Deal',doc.crm_deal,'_assign') or '[]')
        stored=frappe.db.get_value('Marloa Meeting',doc.name,['owner','meeting_owner','crm_deal'],as_dict=True) if doc.name else None
        if stored and stored.crm_deal!=doc.crm_deal:
            if not is_manager(user) or not frappe.has_permission('CRM Deal','write',stored.crm_deal,user=user): return False
        owners=(stored.owner,stored.meeting_owner) if stored else (doc.get('owner'),doc.get('meeting_owner'))
        shared_write=frappe.db.exists('DocShare',{'share_doctype':'CRM Deal','share_name':doc.crm_deal,'user':user,'write':1}) or frappe.db.exists('DocShare',{'share_doctype':'Marloa Meeting','share_name':doc.name,'user':user,'write':1})
        if not (is_manager(user) or user in assigned or user in owners or shared_write):
            return False
    return None


def meeting_query(user=None):
    user = user or frappe.session.user
    names = frappe.get_list('CRM Deal', pluck='name', user=user, limit_page_length=0)
    if not names: return '1=0'
    return '`tabMarloa Meeting`.`crm_deal` in (' + ','.join(frappe.db.escape(n) for n in names) + ')'


def check_calendar(name, actor_connection=None):
    target = frappe.get_doc('Google Calendar', name)
    if not target.enable or not target.push_to_google_calendar:
        frappe.throw('Choose an enabled organizer calendar.', frappe.PermissionError)
    from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
    if target.user == frappe.session.user:
        return get_google_calendar_object(name)
    if not is_manager():
        frappe.throw('Only a manager can manage another employee’s calendar.', frappe.PermissionError)
    own = actor_connection or frappe.db.get_value('Google Calendar', {
        'user':frappe.session.user,'enable':1,'push_to_google_calendar':1}, 'name')
    if not own: frappe.throw('Connect your own Google Calendar first.')
    own_doc = frappe.get_doc('Google Calendar',own)
    if own_doc.user != frappe.session.user:
        frappe.throw('Use your own Google authorization.',frappe.PermissionError)
    service, _ = get_google_calendar_object(own)
    identity = target.user if target.google_calendar_id == 'primary' else target.google_calendar_id
    try:
        entry = service.calendarList().get(calendarId=identity).execute()
    except Exception:
        frappe.throw('Google has not granted your account access to this employee’s calendar.', frappe.PermissionError)
    if entry.get('accessRole') not in ('writer','owner'):
        frappe.throw('Google calendar write access is required to change this invitation.', frappe.PermissionError)
    # The service always uses the ACTING manager's credentials, never the employee's token.
    return service, frappe._dict(name=target.name, user=target.user, google_calendar_id=identity)
