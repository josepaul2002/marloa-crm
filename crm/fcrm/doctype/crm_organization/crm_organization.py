# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from crm.api.exchange_rate import get_exchange_rate


class CRMOrganization(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		address: DF.Link | None
		annual_revenue: DF.Currency
		currency: DF.Link | None
		exchange_rate: DF.Float
		industry: DF.Link | None
		no_of_employees: DF.Literal["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]
		organization_logo: DF.AttachImage | None
		organization_name: DF.Data | None
		territory: DF.Link | None
		website: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self.update_exchange_rate()

	def after_insert(self):
		# Auto-enrich a new Organization from its website (best-effort, background job).
		from crm.domain_enrichment.tasks import auto_enrich_on_create

		auto_enrich_on_create(self)

	def check_deals_before_delete(self):
		deals = frappe.get_all("CRM Deal", filters={"organization": self.name}, pluck="name")
		if deals:
			visible = [name for name in deals if frappe.has_permission("CRM Deal", "read", name)]
			details = ", ".join(visible[:10]) or frappe._("Contact your CRM manager to review the linked deals")
			frappe.throw(
				frappe._("Cannot delete organization {0}: {1} linked deal(s). {2}. Remove or reassign the deals first.").format(
					self.name, len(deals), details
				),
				frappe.LinkExistsError,
			)

	def on_trash(self):
		# Runs for Desk, REST and CRM deletion, after Frappe checks delete permission.
		# Check before any cleanup: a blocked deletion must not change relationships.
		self.check_deals_before_delete()
		frappe.db.delete("Dynamic Link", {"link_doctype": self.doctype, "link_name": self.name,
			"parenttype": ["in", ["Contact", "Address"]]})
		# Preserve notes, tasks, calls and research history; detach only this org's references.
		for doctype, type_field, name_field in (
			("CRM Enrichment Run", "reference_doctype", "reference_name"),
			("FCRM Note", "reference_doctype", "reference_docname"),
			("CRM Task", "reference_doctype", "reference_docname"),
			("CRM Call Log", "reference_doctype", "reference_docname"),
			("CRM Notification", "reference_doctype", "reference_name"),
			("CRM Notification", "notification_type_doctype", "notification_type_doc"),
		):
			frappe.db.set_value(doctype, {type_field: self.doctype, name_field: self.name},
				{type_field: None, name_field: None})
		# The generated people map belongs exclusively to this organization.
		for name in frappe.get_all("Marloa People Map", filters={"organization": self.name}, pluck="name"):
			frappe.delete_doc("Marloa People Map", name, ignore_permissions=True)

	def update_exchange_rate(self):
		if self.has_value_changed("currency") or not self.exchange_rate:
			system_currency = frappe.db.get_single_value("FCRM Settings", "currency") or "USD"
			exchange_rate = 1
			if self.currency and self.currency != system_currency:
				exchange_rate = get_exchange_rate(self.currency, system_currency)

			self.db_set("exchange_rate", exchange_rate)

	@staticmethod
	def default_list_data():
		columns = [
			{
				"label": "Organization",
				"type": "Data",
				"key": "organization_name",
				"width": "16rem",
			},
			{
				"label": "Website",
				"type": "Data",
				"key": "website",
				"width": "14rem",
			},
			{
				"label": "Industry",
				"type": "Link",
				"key": "industry",
				"options": "CRM Industry",
				"width": "14rem",
			},
			{
				"label": "Annual Revenue",
				"type": "Currency",
				"key": "annual_revenue",
				"width": "14rem",
			},
			{
				"label": "Last Modified",
				"type": "Datetime",
				"key": "modified",
				"width": "8rem",
			},
		]
		rows = [
			"name",
			"organization_name",
			"organization_logo",
			"website",
			"industry",
			"currency",
			"annual_revenue",
			"modified",
		]
		return {"columns": columns, "rows": rows}
