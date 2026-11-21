"""Private employee scheduling preferences and shared company places."""
import json
import frappe
from crm.meetings.contacts import require_crm
from crm.meetings.availability_rules import default_preferences, validate_preferences


def read_preferences(user):
    name = frappe.db.get_value('CRM Meeting Preferences', {'user':user}, 'name')
    if not name: return default_preferences(), ''
    doc = frappe.get_doc('CRM Meeting Preferences',name)
    return {**default_preferences(), **json.loads(doc.preferences)}, str(doc.modified)


@frappe.whitelist()
def get_preferences():
    require_crm()
    data, revision = read_preferences(frappe.session.user)
    from crm.meetings.permissions import is_manager
    return {'preferences':data,'revision':revision,'places':shared_places(),'can_manage_places':is_manager(),'places_browser_key':frappe.db.get_single_value('Google Settings','custom_marloa_places_browser_key')}


@frappe.whitelist()
def save_preferences(preferences, revision=''):
    require_crm()
    try:
        data = validate_preferences(json.loads(preferences) if isinstance(preferences,str) else preferences)
    except (ValueError,TypeError,KeyError) as error:
        frappe.throw(str(error))
    user = frappe.session.user
    with frappe.cache.lock('meeting-preferences-'+user, timeout=15, blocking_timeout=3):
        name = frappe.db.get_value('CRM Meeting Preferences', {'user':user}, 'name')
        doc = frappe.get_doc('CRM Meeting Preferences',name) if name else frappe.new_doc('CRM Meeting Preferences')
        if name and str(doc.modified)!=revision:
            frappe.throw('Your availability changed in another window. Reload before saving.')
        doc.user=user;doc.owner=user;doc.preferences=json.dumps(data)
        doc.save(ignore_permissions=True)  # Fixed to the current employee, never a caller-supplied owner.
    from crm.meetings.permissions import is_manager
    return {'preferences':data,'revision':str(doc.modified),'places':shared_places(),'can_manage_places':is_manager(),'places_browser_key':frappe.db.get_single_value('Google Settings','custom_marloa_places_browser_key')}


def shared_places():
    return frappe.get_all('CRM Meeting Place',filters={'enabled':1},fields=['name','label','address'],order_by='label',limit_page_length=100)


@frappe.whitelist()
def directory(deal):
    require_crm()
    doc = frappe.get_doc('CRM Deal',deal);doc.check_permission('read')
    assigned=set(json.loads(doc.get('_assign') or '[]'))
    people=[]
    for user in frappe.get_all('User',filters={'enabled':1,'user_type':'System User','name':['not in',['Administrator','Guest']]},fields=['name','full_name','email'],limit_page_length=500):
        if not set(frappe.get_roles(user.name)) & {'Sales User','Sales Manager','System Manager'}:continue
        prefs,_=read_preferences(user.name)
        people.append({'timezone':prefs['timezone'], 'daily_limit':prefs.get('max_in_person_per_day'), 'buffer_minutes':prefs['buffer_minutes'],'travel_mode':prefs['travel_mode'],'user':user.name,'name':user.full_name or user.name,'email':user.email or user.name,'suggested':user.name in assigned})
    people.sort(key=lambda p:(not p['suggested'],p['name'] or p['user']))
    own, _ = read_preferences(frappe.session.user)
    return {'me':frappe.session.user,'people':people,'own_places':own['places'],'default_place':own['default_place'],
            'travel_mode':own['travel_mode'],'buffer_minutes':own['buffer_minutes'],'shared_places':shared_places()}


@frappe.whitelist()
def list_my_calendars():
    require_crm()
    from crm.meetings.planning import own_service
    service, _ = own_service()
    result=[];page=None
    while True:
        response=service.calendarList().list(maxResults=250,pageToken=page).execute()
        result += [{'id':r['id'],'label':r.get('summary') or r['id'],'access':r.get('accessRole')} for r in response.get('items',[])]
        page=response.get('nextPageToken')
        if not page:break
    return result
