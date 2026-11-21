from frappe.model.document import Document


class CRMMeetingPreferences(Document):
    def validate(self):
        import frappe, json
        from crm.meetings.availability_rules import validate_preferences
        if self.user != frappe.session.user or self.owner != frappe.session.user:
            frappe.throw("Availability settings are private to their employee.", frappe.PermissionError)
        self.preferences = json.dumps(validate_preferences(json.loads(self.preferences or "{}")))
