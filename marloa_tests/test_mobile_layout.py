import copy
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

with patch.dict(sys.modules, {'frappe':types.ModuleType('frappe')}):
 spec=importlib.util.spec_from_file_location('mobile_layout',Path(__file__).parents[1]/'crm/api/marloa_phone.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class LayoutTests(unittest.TestCase):
 def test_removes_only_superseded_country_controls(self):
  original=[{'name':'one','sections':[{'columns':[{'fields':['first_name','mobile_no','custom_mobile_phone_country','custom_whatsapp_uses_the_same_number','custom_whatsapp_country','custom_whatsapp_number','custom_mobile_country']}]}]}]
  before=copy.deepcopy(original)
  result=module.without_country_controls(original)
  self.assertEqual(result[0]['sections'][0]['columns'][0]['fields'],['first_name','mobile_no','custom_whatsapp_uses_the_same_number','custom_whatsapp_country','custom_whatsapp_number'])
  self.assertEqual(original,before)
  self.assertEqual(module.without_country_controls(result),result)
 def test_does_not_remove_unrelated_country_fields_or_field_definitions(self):
  original={'fields':[{'fieldname':'country','label':'Country'},{'fieldname':'custom_mobile_phone_country'},{'fieldname':'custom_whatsapp_country'}]}
  self.assertEqual(module.without_country_controls(original)['fields'],[{'fieldname':'country','label':'Country'},{'fieldname':'custom_whatsapp_country'}])

if __name__=='__main__':unittest.main()
