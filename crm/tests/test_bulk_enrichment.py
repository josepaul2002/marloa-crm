"""Exercise the bulk API boundary without requiring a running Frappe site."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock


class BulkEnrichmentTest(TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).parents[1] / 'domain_enrichment/api.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'bulk_enrich')
        fn.decorator_list = []
        class ValidationError(Exception):
            pass
        self.validation = ValidationError
        def throw(message, exception):
            raise exception(message)
        self.docs = {'A': 'a.example', 'B': '', 'C': 'c.example'}
        self.check = Mock()
        self.enqueue = Mock(return_value={'queued': True})
        env = {'frappe': SimpleNamespace(throw=throw, ValidationError=ValidationError,
            PermissionError=PermissionError, DoesNotExistError=KeyError,
            get_doc=lambda dt, name: {'website': self.docs[name]}, log_error=Mock()),
            '_': lambda s: s, 'get_config': lambda: object(), '_check_writable': self.check,
            '_enqueue_run': self.enqueue, 'cstr': str}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<bulk API>', 'exec'), env)
        self.bulk = env['bulk_enrich']

    def test_deduplicates_and_skips_missing_website(self):
        rows = self.bulk(['A', 'A', 'B'])
        self.assertEqual([r['status'] for r in rows], ['Queued', 'Skipped'])
        self.enqueue.assert_called_once()

    def test_permission_denied_does_not_stop_other_records(self):
        self.check.side_effect = [PermissionError(), None]
        rows = self.bulk(['A', 'C'])
        self.assertEqual([r['status'] for r in rows], ['Failed', 'Queued'])
        self.enqueue.assert_called_once()

    def test_existing_job_is_not_reported_as_new(self):
        self.enqueue.return_value = {'queued': False}
        self.assertEqual(self.bulk(['A'])[0]['status'], 'Running')

    def test_queue_failure_does_not_stop_other_records(self):
        self.enqueue.side_effect = [RuntimeError(), {'queued': True}]
        self.assertEqual([r['status'] for r in self.bulk(['A', 'C'])], ['Failed', 'Queued'])

    def test_rejects_invalid_or_unbounded_selection(self):
        for value in ([], ['A'] * 26, 'A', [None], ['']):
            with self.subTest(value=value), self.assertRaises(self.validation):
                self.bulk(value)
        self.enqueue.assert_not_called()
