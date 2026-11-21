import importlib.util,pathlib,unittest
p=pathlib.Path(__file__).resolve().parents[1]/'meetings'/'event_payload.py'
s=importlib.util.spec_from_file_location('payload',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class PayloadTests(unittest.TestCase):
 def data(self,**kw):return dict(title='Demo',start='2026-12-01T10:00',end='2026-12-01T11:00',invitees='test@gmail.com',**kw)
 def test_timezone(self):self.assertEqual(m.build_payload(self.data())['start']['dateTime'],'2026-12-01T10:00:00+05:30')
 def test_preserves_response(self):self.assertEqual(m.build_payload(self.data(),{'attendees':[{'email':'test@gmail.com','responseStatus':'accepted'}]})['attendees'][0]['responseStatus'],'accepted')
 def test_private_notes_not_exported(self):self.assertNotIn('secret',m.build_payload(self.data(summary='secret'))['description'])
 def test_invalid_order(self):
  d=self.data();d['end']=d['start']
  with self.assertRaises(ValueError):m.build_payload(d)
 def test_drive_only(self):
  with self.assertRaises(ValueError):m.build_payload(self.data(drive_links='https://evil.example/file'))
 def test_repeat(self):self.assertEqual(m.build_payload(self.data(repeat='WEEKLY',repeat_count=4))['recurrence'],['RRULE:FREQ=WEEKLY;COUNT=4'])
 def test_permissions_default(self):self.assertFalse(m.build_payload(self.data())['guestsCanModify'])
 def test_optional_duplicate(self):self.assertEqual(len(m.build_payload(self.data(optional_invitees='test@gmail.com'))['attendees']),1)
if __name__=='__main__':unittest.main()
