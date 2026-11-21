import importlib.util
import pathlib
import unittest
path=pathlib.Path(__file__).resolve().parents[1]/'meetings'/'matching.py'
spec=importlib.util.spec_from_file_location('matching',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class MeetingMatchingTest(unittest.TestCase):
    def test_gmail_exact_match(self):
        result=m.choose_deal(['Mubashir <MUBASHIR.TRAVEL@gmail.com>'],[{'name':'m','emails':['mubashir.travel@gmail.com']}],[{'name':'deal','contacts':['m']}])
        self.assertEqual(result['deal'],'deal')
    def test_no_domain_guessing(self):
        self.assertEqual(m.choose_deal(['other@gmail.com'],[{'name':'m','emails':['mubashir.travel@gmail.com']}],[{'name':'deal','contacts':['m']}])['state'],'needs_linking')
    def test_ambiguous(self):
        self.assertEqual(m.choose_deal(['a@b.in'],[{'name':'a','emails':['a@b.in']}],[{'name':'d1','contacts':['a']},{'name':'d2','contacts':['a']}])['reason'],'multiple_deals')
    def test_explicit_must_be_accessible(self):
        self.assertIsNone(m.choose_deal([],[],[],explicit_deal='secret')['deal'])
    def test_existing_closed_deal_explicit_link_preserved(self):
        self.assertEqual(m.choose_deal([],[],[{'name':'d','closed':True}],explicit_deal='d')['deal'],'d')
    def test_instances_have_distinct_identity(self):
        self.assertNotEqual(m.google_event_identity('c',{'id':'series_1'}),m.google_event_identity('c',{'id':'series_2'}))
    def test_permission_defaults(self):
        self.assertEqual(m.validate_guest_permissions({}),{'guestsCanModify':False,'guestsCanInviteOthers':False,'guestsCanSeeOtherGuests':True})

if __name__=='__main__':unittest.main()
