"""Remove the superseded mobile-country controls without deleting any contact data."""
import json

import frappe

COUNTRY_FIELDS = frozenset({'custom_mobile_country', 'custom_mobile_phone_country'})


def without_country_controls(value):
    """Keep layout order, sections and unrelated fields exactly as configured."""
    if isinstance(value, list):
        return [without_country_controls(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == 'fields' and isinstance(item, list):
            result[key] = [
                without_country_controls(field)
                for field in item
                if (field.get('fieldname') if isinstance(field, dict) else field) not in COUNTRY_FIELDS
            ]
        else:
            result[key] = without_country_controls(item)
    return result


def configure_mobile_input():
    for fieldname in COUNTRY_FIELDS:
        name = frappe.db.get_value('Custom Field', {'dt': 'Contact', 'fieldname': fieldname})
        if name:
            field = frappe.get_doc('Custom Field', name)
            if not field.hidden:
                field.hidden = 1
                field.save(ignore_permissions=True)
    for row in frappe.get_all('CRM Fields Layout', filters={'dt': 'Contact'}, fields=['name', 'layout']):
        if not row.layout:
            continue
        original = json.loads(row.layout)
        updated = without_country_controls(original)
        if updated != original:
            layout = frappe.get_doc('CRM Fields Layout', row.name)
            layout.layout = json.dumps(updated)
            layout.save(ignore_permissions=True)
    frappe.clear_cache(doctype='Contact')
