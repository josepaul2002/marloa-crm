"""Run without a bench: prove disabled/primary-calendar and identity guards."""
import sys,types,unittest,importlib.util,pathlib
from unittest.mock import patch,MagicMock
ROOT=pathlib.Path(__file__).resolve().parents[1]

class SyncGuardTests(unittest.TestCase):
 def load(self):
  fake=types.ModuleType('frappe');fake.session=types.SimpleNamespace(user='employee@example.com');fake.set_user=lambda user:setattr(fake.session,'user',user)
  utils=types.ModuleType('frappe.utils');utils.get_system_timezone=lambda:'Asia/Kolkata'
  crm=types.ModuleType('crm');meetings=types.ModuleType('crm.meetings')
  spec=importlib.util.spec_from_file_location('crm.meetings.matching',ROOT/'meetings/matching.py');matching=importlib.util.module_from_spec(spec);spec.loader.exec_module(matching)
  modules={'frappe':fake,'frappe.utils':utils,'crm':crm,'crm.meetings':meetings,'crm.meetings.matching':matching}
  self.patcher=patch.dict(sys.modules,modules);self.patcher.start();self.addCleanup(self.patcher.stop)
  spec=importlib.util.spec_from_file_location('sync_under_test',ROOT/'meetings/google_sync.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  return module,fake
 def test_user_restored_after_error(self):
  module,fake=self.load()
  with self.assertRaises(RuntimeError):
   with module.calendar_user('other@example.com'):raise RuntimeError()
  self.assertEqual(fake.session.user,'employee@example.com')
 def test_timezone_conversion(self):
  module,_=self.load();self.assertEqual(module.local_datetime('2026-12-01T00:00:00Z'),'2026-12-01 05:30:00')
 def test_shared_calendar_other_owner_not_touched(self):
  module,fake=self.load();fake.db=MagicMock();fake.db.get_value.return_value='inbox'
  fake.get_doc=MagicMock(return_value=types.SimpleNamespace(owner='other@example.com'))
  module.upsert_event(types.SimpleNamespace(google_calendar_id='calendar'),{'id':'event','etag':'v2'})
  fake.db.set_value.assert_not_called()
 def test_unchanged_event_no_duplicate(self):
  module,fake=self.load();fake.db=MagicMock();fake.db.get_value.return_value='inbox'
  fake.get_doc=MagicMock(return_value=types.SimpleNamespace(owner=fake.session.user,etag='same'))
  fake.new_doc=MagicMock()
  module.upsert_event(types.SimpleNamespace(google_calendar_id='calendar'),{'id':'event','etag':'same'})
  fake.new_doc.assert_not_called()

if __name__=='__main__':unittest.main()
