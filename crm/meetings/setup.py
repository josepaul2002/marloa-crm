"""Add opt-in configuration; never switch on primary-calendar imports implicitly."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup():
    fields = {'Google Settings':[{'fieldname':'custom_marloa_routes_server_key','label':'Routes API server key','fieldtype':'Password','description':'Server key restricted to Routes API. Do not use the browser Places key.'},{'fieldname':'custom_marloa_places_browser_key','label':'Restricted Places browser key (sent to browsers)','fieldtype':'Data','hidden':1}], 'Google Calendar':[
        {'fieldname':'custom_marloa_customer_calendar','label':'Dedicated customer meetings calendar confirmed','fieldtype':'Check','default':'0'},
        {'fieldname':'custom_marloa_sync_enabled','label':'Sync customer meetings into CRM','fieldtype':'Check','default':'0'},
        {'fieldname':'custom_marloa_sync_token','label':'CRM calendar sync token','fieldtype':'Password','hidden':1},
        {'fieldname':'custom_marloa_sync_status','label':'CRM sync status','fieldtype':'Small Text','read_only':1},
    ]}
    if frappe.db.exists('DocType','Marloa Meeting'):
        fields['Marloa Meeting']=[
            {'fieldname':'custom_marloa_scheduling_summary','label':'Internal attendees','fieldtype':'Long Text','hidden':1},
            {'fieldname':'custom_google_calendar','label':'Organizer calendar','fieldtype':'Link','options':'Google Calendar','read_only':1},
            {'fieldname':'custom_google_event_id','label':'Google event ID','fieldtype':'Data','read_only':1},
            {'fieldname':'custom_google_etag','label':'Google revision','fieldtype':'Data','hidden':1},
            {'fieldname':'custom_google_request_key','label':'Scheduling request identity','fieldtype':'Data','unique':1,'hidden':1},
            {'fieldname':'custom_google_event_key','label':'Google event identity','fieldtype':'Data','unique':1,'read_only':1},
            {'fieldname':'custom_google_guest_responses','label':'Google guest responses','fieldtype':'Long Text','read_only':1},
            {'fieldname':'custom_google_options','label':'Google meeting options','fieldtype':'Long Text','hidden':1},
        ]
    create_custom_fields(fields, update=True)

    # Preserve the existing restricted public browser key without putting it in git.
    import re
    script_name = 'Marloa Deal Meetings'
    if frappe.db.exists('CRM Form Script', script_name):
        script = frappe.db.get_value('CRM Form Script', script_name, 'script') or ''
        match = re.search(r"const\s+MARLOA_MEETING_GOOGLE_KEY\s*=\s*['\"]([^'\"]+)['\"]", script)
        if match and match.group(1).startswith('AIza'):
            settings=frappe.get_single('Google Settings')
            if not settings.get('custom_marloa_places_browser_key'):
                settings.custom_marloa_places_browser_key=match.group(1)
                settings.save()

        # The native tab replaces the old HTML sidebar and header meeting buttons.
        old_schedule = "  this.actions.push({label:'Schedule meeting',onClick:()=>this.doc.trigger('_marloaScheduleMeeting')});"
        old_record = "  this.actions.push({label:'Record past meeting',onClick:()=>this.doc.trigger('_marloaEditMeeting')});"
        if old_schedule in script and old_record in script:
            script = script.replace(old_schedule, '').replace(old_record, '')
            script = script.replace("  await this.doc.trigger('_marloaRenderMeetings');", "  this.setFieldProperty('custom_marloa_meetings', 'hidden', 1);", 1)
            frappe.db.set_value('CRM Form Script', script_name, 'script', script)
