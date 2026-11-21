import sys,types,unittest,importlib.util,pathlib
from unittest.mock import MagicMock,patch
ROOT=pathlib.Path(__file__).resolve().parents[1]

class AccessRules(unittest.TestCase):
 def load(self,manager=False,access='writer'):
  fake=types.ModuleType('frappe');fake.session=types.SimpleNamespace(user='manager@work.in' if manager else 'viewer@work.in');fake.PermissionError=PermissionError
  fake.get_roles=lambda user=None:['Sales Manager'] if manager else ['Sales User']
  fake.throw=lambda message,*args:(_ for _ in ()).throw(PermissionError(message))
  fake.has_permission=lambda *a,**k:True
  fake._dict=lambda **kw:types.SimpleNamespace(**kw)
  target=types.SimpleNamespace(name='target',user='employee@work.in',enable=1,push_to_google_calendar=1,google_calendar_id='primary')
  own=types.SimpleNamespace(name='own',user=fake.session.user,enable=1,push_to_google_calendar=1,google_calendar_id='primary')
  fake.get_doc=lambda dt,name:target if name=='target' else own
  fake.db=MagicMock();fake.db.exists.return_value=False;fake.db.get_value.return_value='own'
  service=MagicMock();service.calendarList.return_value.get.return_value.execute.return_value={'accessRole':access}
  google=types.ModuleType('frappe.integrations.doctype.google_calendar.google_calendar');google.get_google_calendar_object=MagicMock(return_value=(service,own))
  patcher=patch.dict(sys.modules,{'frappe':fake,'frappe.integrations.doctype.google_calendar.google_calendar':google});patcher.start();self.addCleanup(patcher.stop)
  spec=importlib.util.spec_from_file_location('permission_rules',ROOT/'meetings/permissions.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  return m,fake,google,target
 def test_staff_cannot_use_coworker_calendar(self):
  m,_,google,_=self.load()
  with self.assertRaises(PermissionError):m.check_calendar('target')
  google.get_google_calendar_object.assert_not_called()
 def test_manager_without_google_write_denied(self):
  m,_,google,_=self.load(True,'reader')
  with self.assertRaises(PermissionError):m.check_calendar('target')
  google.get_google_calendar_object.assert_called_once_with('own')
 def test_manager_uses_own_token_and_target_identity(self):
  m,_,google,target=self.load(True)
  _,account=m.check_calendar('target')
  google.get_google_calendar_object.assert_called_once_with('own')
  self.assertEqual(account.google_calendar_id,'employee@work.in')
  self.assertEqual(target.google_calendar_id,'primary')
 def test_viewer_cannot_gain_write_by_changing_owner(self):
  m,fake,_,_=self.load()
  stored=types.SimpleNamespace(owner='employee@work.in',meeting_owner='employee@work.in',crm_deal='DEAL-1')
  fake.db.get_value.side_effect=lambda dt,*args,**kw:'[]' if dt=='CRM Deal' else stored
  doc=types.SimpleNamespace(name='MEETING-1',crm_deal='DEAL-1',get=lambda key: {'crm_deal':'DEAL-1','owner':fake.session.user,'meeting_owner':fake.session.user}.get(key))
  self.assertFalse(m.meeting_has_permission(doc,'write',fake.session.user))
 def test_deal_denial_also_denies_meeting_read(self):
  m,fake,_,_=self.load(True);fake.has_permission=lambda *a,**kw:False
  doc=types.SimpleNamespace(crm_deal='DEAL-1',get=lambda key:'DEAL-1')
  self.assertFalse(m.meeting_has_permission(doc,'read',fake.session.user))
if __name__=='__main__':unittest.main()
