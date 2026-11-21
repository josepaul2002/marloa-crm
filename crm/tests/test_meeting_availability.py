import unittest,importlib.util,pathlib
from datetime import datetime,timezone
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rules',ROOT/'meetings/availability_rules.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class AvailabilityRules(unittest.TestCase):
 def preferences(self):
  p=r.default_preferences();p['weekly']={m:[[['09:00','18:00']] for _ in range(7)] for m in r.MODES}
  return r.validate_preferences(p)
 def instant(self,value):return r.aware(value,'Asia/Kolkata')
 def person(self):return {'user':'a','required':True,'preferences':self.preferences(),'busy':[],'buffer':15,'travel_minutes':40,'calendar_error':None}
 def test_weekend_on_and_monday_off(self):
  p=self.preferences();p['weekly']['Online'][0]=[]
  self.assertFalse(r.working_window(p,self.instant('2026-11-23 10:00'),self.instant('2026-11-23 11:00'),'Online'))
  self.assertTrue(r.working_window(p,self.instant('2026-11-28 10:00'),self.instant('2026-11-28 11:00'),'Online'))
 def test_date_override_replaces_week(self):
  p=self.preferences();p['exceptions']=[{'date':'2026-11-24','mode':'Online','windows':[]}]
  self.assertFalse(r.working_window(p,self.instant('2026-11-24 10:00'),self.instant('2026-11-24 11:00'),'Online'))
  self.assertTrue(r.working_window(p,self.instant('2026-11-24 10:00'),self.instant('2026-11-24 11:00'),'In person'))
 def test_split_windows_exclude_lunch(self):
  p=self.preferences();p['weekly']['Online'][1]=[['09:00','12:00'],['14:00','18:00']]
  self.assertFalse(r.working_window(p,self.instant('2026-11-24 11:30'),self.instant('2026-11-24 14:30'),'Online'))
 def test_unknown_not_free(self):
  p=self.person();p['calendar_error']='denied'
  self.assertEqual(r.candidate_status(p,self.instant('2026-11-24 10:00'),self.instant('2026-11-24 11:00'),'Online'),'unknown')
 def test_unconfigured_not_free(self):
  p=self.person();p['preferences']['configured']=False
  self.assertEqual(r.candidate_status(p,self.instant('2026-11-24 10:00'),self.instant('2026-11-24 11:00'),'Online'),'unknown')
 def test_travel_blocks_gap_after_previous_meeting(self):
  p=self.person();p['busy']=[(self.instant('2026-11-24 09:00'),self.instant('2026-11-24 10:30'))]
  self.assertEqual(r.candidate_status(p,self.instant('2026-11-24 11:00'),self.instant('2026-11-24 11:30'),'In person'),'travel_conflict')
  self.assertEqual(r.candidate_status(p,self.instant('2026-11-24 11:25'),self.instant('2026-11-24 11:55'),'In person'),'free')
 def test_online_does_not_require_travel(self):
  p=self.person();p['travel_minutes']=None
  self.assertEqual(r.candidate_status(p,self.instant('2026-11-24 10:00'),self.instant('2026-11-24 11:00'),'Online'),'free')
 def test_unavailable_route_not_zero(self):
  p=self.person();p['travel_minutes']=None
  self.assertEqual(r.candidate_status(p,self.instant('2026-11-24 10:00'),self.instant('2026-11-24 11:00'),'In person'),'unknown')
 def test_optional_conflict_does_not_block_required(self):
  a=self.person();b=self.person();b['user']='b';b['required']=False;b['calendar_error']='no access'
  slots=r.build_slots([a,b],self.instant('2026-11-24 10:00'),self.instant('2026-11-24 11:00'),30,'Online','Asia/Kolkata')
  self.assertTrue(slots[0]['available']);self.assertEqual(slots[0]['optional_conflicts'],1)
 def test_timezone_is_employee_local(self):
  p=self.preferences();p['timezone']='Australia/Sydney'
  self.assertTrue(r.working_window(p,r.aware('2026-11-24 09:00','Australia/Sydney'),r.aware('2026-11-24 10:00','Australia/Sydney'),'Online'))
  self.assertFalse(r.working_window(p,r.aware('2026-11-24 09:00','UTC'),r.aware('2026-11-24 10:00','UTC'),'Online'))
 def test_nonexistent_dst_time_rejected(self):
  with self.assertRaises(ValueError):r.aware('2026-10-04 02:30','Australia/Sydney')
 def test_overlap_and_invalid_range_rejected(self):
  for value in [[['12:00','09:00']],[['09:00','12:00'],['11:00','13:00']]]:
   with self.assertRaises(ValueError):r.windows(value)
 def test_adjacent_busy_period_not_conflict(self):
  p=self.person();p['busy']=[(self.instant('2026-11-24 09:00'),self.instant('2026-11-24 10:00'))]
  self.assertEqual(r.candidate_status(p,self.instant('2026-11-24 10:00'),self.instant('2026-11-24 11:00'),'Online'),'free')
 def test_invalid_default_place_rejected(self):
  p=self.preferences();p['default_place']='not-existing'
  with self.assertRaises(ValueError):r.validate_preferences(p)
 def test_explicit_cutoff_excludes_past(self):
  slots=r.build_slots([self.person()],self.instant('2026-11-24 10:00'),self.instant('2026-11-24 11:00'),30,'Online','Asia/Kolkata',self.instant('2026-11-24 10:20'))
  self.assertEqual(len(slots),1);self.assertIn('10:30',slots[0]['start'])
if __name__=='__main__':unittest.main()
