"""Organization deletion policy regression tests, independent of a running site."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


class OrganizationDeletionTest(TestCase):
    def setUp(self):
        source = Path(__file__).parents[1] / 'fcrm/doctype/crm_organization/crm_organization.py'
        cls = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef))
        cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('on_trash', 'check_deals_before_delete')]
        class Linked(Exception):
            pass
        self.Linked = Linked
        def throw(message, exception):
            raise exception(message)
        self.frappe = SimpleNamespace(get_all=Mock(return_value=[]), db=SimpleNamespace(delete=Mock(), set_value=Mock()),
            has_permission=Mock(return_value=True), throw=throw, LinkExistsError=Linked, _=lambda s: s,
            delete_doc=Mock())
        env = {'frappe': self.frappe, 'Document': object}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), '<organization>', 'exec'), env)
        self.doc = env['CRMOrganization']()
        self.doc.name = 'Policy Test'
        self.doc.doctype = 'CRM Organization'

    def test_deal_blocks_before_relationships_are_changed(self):
        self.frappe.get_all.return_value = ['DEAL-1']
        with self.assertRaisesRegex(self.Linked, 'DEAL-1'):
            self.doc.on_trash()
        self.frappe.db.delete.assert_not_called()
        self.frappe.db.set_value.assert_not_called()
        self.frappe.delete_doc.assert_not_called()

    def test_hidden_deals_still_block_without_exposing_names(self):
        self.frappe.get_all.return_value = ['CONFIDENTIAL-DEAL']
        self.frappe.has_permission.return_value = False
        with self.assertRaises(self.Linked) as err:
            self.doc.on_trash()
        self.assertNotIn('CONFIDENTIAL-DEAL', str(err.exception))
        self.assertIn('1 linked deal', str(err.exception))

    def test_contacts_and_addresses_preserved_only_relationship_rows_removed(self):
        self.doc.on_trash()
        self.frappe.db.delete.assert_called_once_with('Dynamic Link', {
            'link_doctype': 'CRM Organization', 'link_name': 'Policy Test',
            'parenttype': ['in', ['Contact', 'Address']]})
        self.frappe.delete_doc.assert_not_called()
        self.frappe.db.set_value.assert_any_call('CRM Enrichment Run',
            {'reference_doctype': 'CRM Organization', 'reference_name': 'Policy Test'},
            {'reference_doctype': None, 'reference_name': None})

    def test_only_exclusively_owned_generated_people_map_deleted(self):
        self.frappe.get_all.side_effect = [[], ['MAP-1']]
        self.doc.on_trash()
        self.frappe.delete_doc.assert_called_once_with('Marloa People Map', 'MAP-1', ignore_permissions=True)

    def test_bulk_preflights_all_deals_and_permissions_before_any_delete(self):
        source = Path(__file__).parents[1] / 'api/doc.py'
        fn = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'delete_bulk_docs')
        fn.decorator_list = []
        # Remove unrelated legacy bulk implementation's local import for this isolated policy test.
        fn.body = [n for n in fn.body if not isinstance(n, ast.ImportFrom)]
        first = SimpleNamespace(check_permission=Mock(), check_deals_before_delete=Mock())
        second = SimpleNamespace(check_permission=Mock(), check_deals_before_delete=Mock(side_effect=self.Linked('blocked')))
        self.frappe.get_doc = Mock(side_effect=[first, second])
        self.frappe.parse_json = lambda value: value
        env = {'frappe': self.frappe, '_': lambda s: s}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<bulk>', 'exec'), env)
        with self.assertRaises(self.Linked):
            env['delete_bulk_docs']('CRM Organization', ['A', 'B'], delete_linked=True)
        self.frappe.delete_doc.assert_not_called()
        first.check_permission.assert_called_once_with('delete')
        second.check_permission.assert_called_once_with('delete')
