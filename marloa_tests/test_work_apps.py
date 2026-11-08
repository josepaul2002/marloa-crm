"""Isolated API contract tests; run: python3 -m unittest discover -s marloa_tests."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

class Row(dict):
 def __getattr__(self,k): return self.get(k)
 def __setattr__(self,k,v): self[k]=v

class PermissionError_(Exception): pass
class ValidationError(Exception): pass

class Doc(Row):
 def save(self,ignore_permissions=False):
  if self.doctype=='Marloa Work App Preferences':
   assert self.user==fake.session.user
   assert ignore_permissions
   self.name=self.user
  else:
   assert 'System Manager' in fake.get_roles()
   self.name=self.name or 'new-company'
  self.modified=str(int(self.modified or '0')+1)
  store[(self.doctype,self.name)]=copy.deepcopy(self)
  return self

store={}
fake=types.ModuleType('frappe');fake._=lambda x:x;fake.PermissionError=PermissionError_
def throw(msg,cls=ValidationError): raise cls(msg)
fake.throw=throw;fake.whitelist=lambda **kw: lambda f:f
fake.session=Row(user='alice@marloa.in')
fake.get_roles=lambda:['Sales User']
fake.get_all=lambda dt,**kw: [Row(copy.deepcopy(v)) for (kind,k),v in store.items() if kind==dt]
fake.get_doc=lambda dt,name: Doc(dict(copy.deepcopy(store[(dt,name)]),doctype=dt))
fake.new_doc=lambda dt: Doc(doctype=dt)
def get_value(dt,name,fields,**kw):
 return Row(copy.deepcopy(store.get((dt,name),{}))) or None
fake.db=Row(get_value=get_value,exists=lambda dt,name:(dt,name) in store)
crm_api=types.ModuleType('crm.api');crm_api.check_app_permission=lambda:True
with patch.dict(sys.modules,{'frappe':fake,'crm.api':crm_api}):
 spec=importlib.util.spec_from_file_location('work_apps',Path(__file__).parents[1]/'crm/api/marloa_work_apps.py')
 api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)

class WorkAppsTests(unittest.TestCase):
 def setUp(self):
  store.clear();fake.session.user='alice@marloa.in';fake.get_roles=lambda:['Sales User']
  store[(api.APPS,'gmail')]=Row(name='gmail',title='Gmail',url='https://mail.google.com/',category='Google',enabled=1,modified='1')
 def settings(self):return {'personal':[{'id':'personal:one','title':'Example','url':'https://example.com/','category':'My apps'}],'choices':{'company:gmail':{'pinned':True,'hidden':False,'order':1}}}
 def test_private_preferences_follow_session_only(self):
  saved=api.save_preferences(self.settings())
  self.assertEqual(saved['settings']['personal'][0]['title'],'Example')
  fake.session.user='bob@marloa.in'
  self.assertEqual(api.get_apps()['settings'],api.empty_settings())
  self.assertEqual(api.get_apps()['revision'],'')
  api.save_preferences(api.empty_settings())
  fake.session.user='alice@marloa.in'
  self.assertEqual(api.get_apps()['settings']['personal'][0]['title'],'Example')
 def test_cannot_supply_another_user(self):
  with self.assertRaises(TypeError):api.save_preferences(self.settings(),user='bob@marloa.in')
 def test_stale_revision_does_not_overwrite(self):
  api.save_preferences(self.settings())
  with self.assertRaises(ValidationError):api.save_preferences(api.empty_settings(),revision='')
  self.assertTrue(api.get_apps()['settings']['personal'])
 def test_company_changes_require_admin(self):
  with self.assertRaises(PermissionError_):api.save_company_app('X','https://example.com/')
 def test_guest_blocked(self):
  fake.session.user='Guest'
  with self.assertRaises(PermissionError_):api.get_apps()
 def test_non_crm_user_blocked(self):
  with patch.object(api,'check_app_permission',return_value=False):
   with self.assertRaises(PermissionError_):api.get_apps()
 def test_dangerous_urls_rejected(self):
  for url in ['javascript:alert(1)','data:text/html,a','http://example.com','https://user:pass@example.com','https://a.com\\@evil.com','https://a.com:444','https://example.com/\n']:
   with self.subTest(url=url),self.assertRaises(ValidationError):api.clean_url(url)
 def test_company_disable_and_revision(self):
  fake.get_roles=lambda:['System Manager']
  result=api.save_company_app('Gmail','https://mail.google.com/','Google',app_id='company:gmail',enabled=False,revision='1')
  self.assertFalse(result['company'][0]['enabled'])
  with self.assertRaises(ValidationError):api.save_company_app('Changed','https://example.com/','Google',app_id='company:gmail',revision='1')
  fake.get_roles=lambda:['Sales User']
  self.assertEqual(api.get_apps()['company'],[])
 def test_preferences_reject_duplicate_ids_and_limit(self):
  value=self.settings();value['personal']*=2
  with self.assertRaises(ValidationError):api.parse_settings(value,[])
  with self.assertRaises(ValidationError):api.parse_settings({'personal':[{}]*81},[])
 def test_foreign_choices_ignored(self):
  value=self.settings();value['choices']['personal:someone-elses']={'pinned':True}
  result=api.parse_settings(value,['company:gmail'])
  self.assertNotIn('personal:someone-elses',result['choices'])
 def test_all_seed_urls_valid_unique(self):
  self.assertEqual(len(set(u for _,u,_ in api.DEFAULTS)),11)
  for _,url,_ in api.DEFAULTS:self.assertEqual(api.clean_url(url),url)

if __name__=='__main__':unittest.main()
