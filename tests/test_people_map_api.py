"""Permission, concurrency and provider contracts without a live Frappe site."""
import importlib.util
import json
import pathlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

root = pathlib.Path(__file__).parents[1]
# Stand-ins keep these tests from needing a production database or credentials.
frappe = types.ModuleType('frappe')
frappe.whitelist = lambda: lambda f: f
frappe.utils = types.ModuleType('frappe.utils')
for n in ('now_datetime', 'get_datetime', 'today'):
    setattr(frappe.utils, n, MagicMock())
requests = types.ModuleType('requests')
requests.post = MagicMock()
sys.modules.setdefault('frappe', frappe)
sys.modules.setdefault('frappe.utils', frappe.utils)
sys.modules.setdefault('requests', requests)
sys.path.insert(0, str(root))
package = types.ModuleType('crm.api')
package.__path__ = [str(root / 'crm/api')]
sys.modules['crm.api'] = package
spec = importlib.util.spec_from_file_location('people_api', root/'crm/api/marloa_people_map.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


def throw(message, *args):
    raise ValueError(message)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.f = patch.object(api, 'frappe', MagicMock()).start()
        self.f.throw.side_effect = throw
        self.addCleanup(patch.stopall)

    def test_read_checks_organization_permission_before_loading(self):
        self.f.get_doc.return_value.check_permission.side_effect = PermissionError
        with self.assertRaises(PermissionError):
            api.get_map('private-company')
        self.f.db.exists.assert_not_called()

    def test_save_rejects_stale_revision(self):
        doc = types.SimpleNamespace(revision=5)
        with patch.object(api, '_locked_map', return_value=doc):
            with self.assertRaisesRegex(ValueError, 'changed'):
                api.save_map('company', '[]', 4)

    def test_client_cannot_inject_a_contact_link(self):
        doc = MagicMock()
        doc.revision = 0
        doc.people_json = '[]'
        with patch.object(api, '_locked_map', return_value=doc), patch.object(api, 'get_map', return_value={}):
            api.save_map('company', [{'id':'a','name':'A','contact':'private-contact'}], 0)
        self.assertEqual(json.loads(doc.people_json)[0]['contact'], '')

    def test_missing_key_does_not_queue_or_call_provider(self):
        with patch.object(api, '_config', return_value=None):
            with self.assertRaisesRegex(ValueError, 'configure'):
                api.start_research('company')
        self.f.enqueue.assert_not_called()

    def test_contact_permission_is_required(self):
        self.f.has_permission.return_value = False
        with self.assertRaisesRegex(ValueError, 'permission'):
            api.add_contact('company', 'a')

    def test_duplicate_contact_is_not_overwritten(self):
        self.f.has_permission.return_value = True
        self.f.get_list.return_value = ['existing']
        doc = types.SimpleNamespace(people_json='[{"id":"a","name":"A","title":"Head"}]')
        with patch.object(api, '_locked_map', return_value=doc):
            with self.assertRaisesRegex(ValueError, 'already exists'):
                api.add_contact('company', 'a')

    def test_provider_sources_collected_from_nested_blocks(self):
        result = api._source_urls([{'type':'web_search_tool_result','content':[{'url':'https://example.com/team'}]}])
        self.assertEqual(result, {'https://example.com/team'})

    def test_pdl_request_is_bounded_and_no_personal_data_is_forwarded(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {'data':[{'full_name':'A','job_title':'Director','work_email':'secret@example.com','linkedin_url':'linkedin.com/in/a'}]}
        with patch.object(api, '_config', return_value='test-key'), patch.object(api.requests, 'post', return_value=response) as post:
            data = api._pdl_candidates('example.com')
        self.assertNotIn('work_email', data[0])
        self.assertEqual(post.call_args.kwargs['json']['size'], 10)

if __name__ == '__main__':
    unittest.main()
