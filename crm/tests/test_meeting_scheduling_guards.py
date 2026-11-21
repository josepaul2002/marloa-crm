import sys,types,unittest,importlib.util,pathlib
from unittest.mock import MagicMock,patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
class SchedulingGuards(unittest.TestCase):
 def load(self):
  fake=types.ModuleType('frappe');fake.session=types.SimpleNamespace(user='owner@example.com');fake.whitelist=lambda *a,**k:lambda fn:fn;fake.PermissionError=PermissionError
  def fail(message,*args):raise PermissionError(message)
  fake.throw=fail
  payload=types.ModuleType('crm.meetings.event_payload');payload.build_payload=MagicMock()
  sync=types.ModuleType('crm.meetings.google_sync');sync.local_datetime=lambda v:v
  modules={'frappe':fake,'crm.meetings.event_payload':payload,'crm.meetings.google_sync':sync}
  patcher=patch.dict(sys.modules,modules);patcher.start();self.addCleanup(patcher.stop)
  spec=importlib.util.spec_from_file_location('schedule_under_test',ROOT/'meetings/scheduling.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  return module,fake
 def test_other_employee_calendar_denied(self):
  module,fake=self.load();fake.get_doc=lambda *a:types.SimpleNamespace(user='other@example.com',enable=1,push_to_google_calendar=1)
  with self.assertRaises(PermissionError):module.calendar_for_user('calendar')
 def test_disabled_calendar_denied(self):
  module,fake=self.load();fake.get_doc=lambda *a:types.SimpleNamespace(user=fake.session.user,enable=0,push_to_google_calendar=1)
  with self.assertRaises(PermissionError):module.calendar_for_user('calendar')
 def test_timeout_is_not_treated_as_missing(self):
  module,_=self.load();service=MagicMock();service.events.return_value.get.return_value.execute.side_effect=TimeoutError()
  with self.assertRaises(TimeoutError):module.get_current_event(service,'c','e',True)
 def test_404_only_recoverable_when_pending(self):
  module,_=self.load();service=MagicMock();error=RuntimeError();error.resp=types.SimpleNamespace(status=404)
  service.events.return_value.get.return_value.execute.side_effect=error
  self.assertIsNone(module.get_current_event(service,'c','e',True))
  with self.assertRaises(RuntimeError):module.get_current_event(service,'c','e',False)
if __name__=='__main__':unittest.main()
