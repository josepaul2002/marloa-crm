import frappe
from frappe.model.document import Document


class CRMCalendarInbox(Document):
    def validate(self):
        if self.owner and self.owner != frappe.session.user and frappe.session.user != 'Administrator':
            frappe.throw('Calendar meetings are private to their owner.', frappe.PermissionError)
        if self.deal:
            frappe.get_doc('CRM Deal', self.deal).check_permission('read')
        if self.meeting:
            meeting = frappe.get_doc('Marloa Meeting', self.meeting)
            meeting.check_permission('read')
            if meeting.crm_deal != self.deal:
                frappe.throw('Meeting and selected deal must match.')
