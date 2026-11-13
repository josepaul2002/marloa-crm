import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('validation', pathlib.Path(__file__).parents[1] / 'crm/api/people_map_validation.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class ValidationTests(unittest.TestCase):
    def test_cycles_and_unknown_managers(self):
        for people in ([{'id':'a','name':'A','manager_id':'a','relationship':'confirmed'}],
                       [{'id':'a','name':'A','manager_id':'missing','relationship':'confirmed'}]):
            with self.assertRaises(ValueError):
                v.validate_people(people)

    def test_research_cannot_confirm_relationships(self):
        result = v.validate_people([{'id':'a','name':'A','sources':['https://example.com/team']},
            {'id':'b','name':'B','sources':['https://example.com/team'],'manager_id':'a',
             'relationship':'confirmed','relationship_evidence':'B reports to A'}], researched=True)
        self.assertEqual(result[1]['relationship'], 'sourced')

    def test_unsupported_claims_do_not_get_edges(self):
        result = v.validate_people([{'id':'a','name':'A','sources':['https://example.com/team'],
            'relationship':'inferred','manager_id':'missing'}], researched=True)
        self.assertEqual(result[0]['manager_id'], '')

    def test_requires_sources_and_safe_linkedin(self):
        for person in ({'name':'A'}, {'name':'A','sources':['https://example.com'], 'linkedin_url':'javascript:alert(1)'}):
            with self.assertRaises(ValueError):
                v.validate_people([person], researched=True)

    def test_does_not_store_unrequested_personal_data(self):
        self.assertNotIn('email', v.validate_people([{'name':'A', 'email':'private@example.com'}])[0])

if __name__ == '__main__':
    unittest.main()
