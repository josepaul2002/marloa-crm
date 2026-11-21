import sys,types,unittest,importlib.util,pathlib
from unittest.mock import MagicMock,patch
ROOT=pathlib.Path(__file__).resolve().parents[1]

class PlanningGuards(unittest.TestCase):
 def load(self):
  f=types.ModuleType('frappe');f.session=types.SimpleNamespace(user='owner@work.in');f.PermissionError=PermissionError
  f.whitelist=lambda *a,**kw:lambda fn:fn
  f.throw=lambda message,*args:(_ for _ in ()).throw(ValueError(message))
  f.db=MagicMock();f.db.exists.return_value=True;f.db.get_value.side_effect=lambda dt,name,field:name;f.get_roles=lambda u:['Sales User'];f.get_doc=MagicMock()
  contacts=types.ModuleType('crm.meetings.contacts');contacts.require_crm=lambda:None
  prefs=types.ModuleType('crm.meetings.preferences')
  rate=types.ModuleType('frappe.rate_limiter');rate.rate_limit=lambda *a,**kw:lambda fn:fn
  spec=importlib.util.spec_from_file_location('crm.meetings.availability_rules',ROOT/'meetings/availability_rules.py');rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(rules)
  p=rules.default_preferences();p['configured']=True;p['weekly']={m:[[['09:00','18:00']] for _ in range(7)] for m in rules.MODES}
  p['places']=[{'id':'home','label':'Home','address':'PRIVATE ADDRESS'}];p['default_place']='home'
  prefs.read_preferences=lambda user:(p,'v1')
  perms=types.ModuleType('crm.meetings.permissions');perms.is_manager=lambda:False
  patcher=patch.dict(sys.modules,{'frappe':f,'frappe.rate_limiter':rate,'crm.meetings.contacts':contacts,'crm.meetings.preferences':prefs,'crm.meetings.availability_rules':rules,'crm.meetings.permissions':perms});patcher.start();self.addCleanup(patcher.stop)
  spec=importlib.util.spec_from_file_location('planning_under_test',ROOT/'meetings/planning.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  return m,f,p,perms
 def request(self):return {'from':'2030-01-01 09:00','to':'2030-01-01 12:00','duration':30,'timezone':'Asia/Kolkata','mode':'Online','attendees':[{'user':'employee@work.in','required':True}]}
 def test_private_origin_requires_employee_opt_in(self):
  m,f,p,_=self.load();row={'user':'employee@work.in','origin_source':'default'}
  self.assertEqual(m.origin_for(row,p),'')
  p['share_travel_estimate']=True;self.assertEqual(m.origin_for(row,p),'PRIVATE ADDRESS')
 def test_other_person_cannot_select_private_place_by_id(self):
  m,_,p,_=self.load();p['share_travel_estimate']=True
  self.assertEqual(m.origin_for({'user':'other@work.in','origin_source':'personal','origin_id':'home'},p),'')
 def test_owner_can_use_own_place(self):
  m,f,p,_=self.load()
  self.assertEqual(m.origin_for({'user':f.session.user,'origin_source':'personal','origin_id':'home'},p),'PRIVATE ADDRESS')
 def test_calendar_denial_produces_unknown_not_free(self):
  m,_,_,_=self.load();service=MagicMock();service.freebusy.return_value.query.return_value.execute.return_value={'calendars':{'employee@work.in':{'errors':[{'reason':'notFound'}]}}};m.own_service=lambda:(service,None)
  result=m.plan('DEAL',self.request())
  self.assertEqual(result['suggestions'],[])
  self.assertEqual(result['slots'][0]['people'][0]['status'],'unknown')
  self.assertNotIn('PRIVATE ADDRESS',str(result))
 def test_result_does_not_expose_private_preferences(self):
  m,_,_,_=self.load();service=MagicMock();service.freebusy.return_value.query.return_value.execute.return_value={'calendars':{'employee@work.in':{'busy':[]}}};m.own_service=lambda:(service,None)
  result=m.plan('DEAL',self.request());self.assertTrue(result['suggestions'])
  self.assertNotIn('PRIVATE ADDRESS',str(result));self.assertNotIn('places',result['people'][0])
 def test_missing_physical_location_rejected(self):
  m,_,_,_=self.load();data=self.request();data['mode']='In person'
  with self.assertRaises(ValueError):m.parse_request(data)
 def test_disabled_employee_rejected(self):
  m,f,_,_=self.load();f.db.exists.return_value=False
  with self.assertRaises(ValueError):m.parse_request(self.request())
 def test_conflict_requires_manager_even_with_reason(self):
  m,_,_,_=self.load();m.plan=lambda *a,**kw:{'slots':[{'people':[{'user':'a','required':True,'status':'busy'}]}]}
  data={'start':'2030-01-01 10:00','end':'2030-01-01 11:00','internal_attendees':[{'user':'a'}],'availability_override_reason':'Approved after discussion'}
  with self.assertRaises(ValueError):m.check_before_send('DEAL',data)
 def test_manager_conflict_requires_reason(self):
  m,_,_,perms=self.load();perms.is_manager=lambda:True;m.plan=lambda *a,**kw:{'slots':[{'people':[{'user':'a','required':True,'status':'unknown'}]}]}
  data={'start':'2030-01-01 10:00','end':'2030-01-01 11:00','internal_attendees':[{'user':'a'}]}
  with self.assertRaises(ValueError):m.check_before_send('DEAL',data)
  data['availability_override_reason']='Confirmed directly with attendee';_,reason=m.check_before_send('DEAL',data)
  self.assertEqual(reason,data['availability_override_reason'])
 def test_required_selection_cannot_be_omitted(self):
  m,_,_,_=self.load()
  with self.assertRaises(ValueError):m.check_before_send('DEAL',{'start':'2030-01-01','end':'2030-01-02'})
if __name__=='__main__':unittest.main()
