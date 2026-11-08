"""Company navigation and per-user shortcuts. Never proxies websites or stores credentials."""
import json
from urllib.parse import urlsplit

import frappe
from frappe import _
from crm.api import check_app_permission

APPS = 'Marloa Work App'
PREFS = 'Marloa Work App Preferences'
DEFAULTS = [
 ('Gmail','https://mail.google.com/','Google'),
 ('Google Drive','https://drive.google.com/','Google'),
 ('Customer documents','https://drive.google.com/drive/shared-drives','Google'),
 ('Google Calendar','https://calendar.google.com/','Google'),
 ('Google Meet','https://meet.google.com/','Google'),
 ('ChatGPT','https://chatgpt.com/','AI'),
 ('Claude','https://claude.ai/','AI'),
 ('Marloa customer dashboard','https://app.marloa.in/sign-in?redirect=%2F','Marloa'),
 ('Marloa staff console','https://admin-1215.marloa.in/sign-in?redirect=%2F','Marloa'),
 ('Marloa customer dashboard (DEV)','https://app-6423.dev.marloa.in/sign-in?redirect=%2F','Development'),
 ('Marloa staff console (DEV)','https://admin-6423.dev.marloa.in/sign-in?redirect=%2F','Development'),
]


def require_user():
 if frappe.session.user == 'Guest' or not check_app_permission():
  frappe.throw(_('CRM access is required.'), frappe.PermissionError)


def require_admin():
 require_user()
 if 'System Manager' not in frappe.get_roles():
  frappe.throw(_('Only a System Manager can change company apps.'), frappe.PermissionError)


def clean_text(value, limit):
 if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
  frappe.throw(_('Enter a valid name or category.'))
 return value.strip()


def clean_url(value):
 if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value) or '\\' in value:
  frappe.throw(_('Enter a valid HTTPS website URL.'))
 try:
  parsed = urlsplit(value)
  if parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None:
   raise ValueError()
  if parsed.port not in (None, 443):
   raise ValueError()
 except ValueError:
  frappe.throw(_('Use an HTTPS website URL without embedded credentials or a custom port.'))
 return value


def empty_settings():
 return {'personal': [], 'choices': {}}


def parse_settings(value, company_ids):
 if isinstance(value, str):
  if len(value) > 100000: frappe.throw(_('Too many shortcuts.'))
  try: value=json.loads(value)
  except (ValueError, TypeError): frappe.throw(_('Invalid shortcut settings.'))
 if not isinstance(value, dict): frappe.throw(_('Invalid shortcut settings.'))
 personal=value.get('personal', []); choices=value.get('choices', {})
 if not isinstance(personal,list) or len(personal)>80 or not isinstance(choices,dict) or len(choices)>300:
  frappe.throw(_('Too many shortcuts.'))
 result=empty_settings(); seen=set()
 for item in personal:
  if not isinstance(item,dict): frappe.throw(_('Invalid shortcut.'))
  key=item.get('id','')
  if not isinstance(key,str) or not key.startswith('personal:') or len(key)>80 or key in seen:
   frappe.throw(_('Invalid shortcut identifier.'))
  seen.add(key)
  result['personal'].append({'id':key,'title':clean_text(item.get('title'),100),'url':clean_url(item.get('url')),'category':clean_text(item.get('category') or 'My apps',60)})
 valid=seen|set(company_ids)
 for key, choice in choices.items():
  if key not in valid: continue
  if not isinstance(choice,dict): frappe.throw(_('Invalid shortcut preference.'))
  order=choice.get('order',0)
  if isinstance(order,bool) or not isinstance(order,int) or not -10000<=order<=10000:
   frappe.throw(_('Invalid shortcut order.'))
  result['choices'][key]={'pinned':bool(choice.get('pinned')), 'hidden':bool(choice.get('hidden')), 'order':order}
 return result


@frappe.whitelist(methods=['GET','POST'])
def get_apps():
 require_user()
 # No client-supplied user: private settings always belong to the authenticated session.
 rows=frappe.get_all(APPS,fields=['name','title','url','category','enabled','modified'],order_by='creation asc')
 admin='System Manager' in frappe.get_roles()
 company=[dict(id='company:'+r.name,title=r.title,url=r.url,category=r.category,enabled=bool(r.enabled),modified=str(r.modified)) for r in rows if r.enabled or admin]
 pref=frappe.db.get_value(PREFS,frappe.session.user,['settings','modified'],as_dict=True)
 return {'company':company,'settings':json.loads(pref.settings) if pref and pref.settings else empty_settings(),'revision':str(pref.modified) if pref else '', 'can_manage':admin}


@frappe.whitelist(methods=['POST'])
def save_preferences(settings, revision=''):
 require_user()
 ids=['company:'+r.name for r in frappe.get_all(APPS,fields=['name'])]
 clean=parse_settings(settings,ids)
 name=frappe.session.user
 if frappe.db.exists(PREFS,name):
  doc=frappe.get_doc(PREFS,name)
  if str(doc.modified)!=revision:
   frappe.throw(_('Your shortcuts changed in another window. Reload Work apps and try again.'))
 else:
  if revision: frappe.throw(_('Reload Work apps before saving.'))
  doc=frappe.new_doc(PREFS);doc.user=name
 doc.settings=json.dumps(clean)
 # Narrow bypass: table is not generally accessible; target is exclusively the session user.
 doc.save(ignore_permissions=True)
 return get_apps()


@frappe.whitelist(methods=['POST'])
def save_company_app(title, url, category='Company', app_id=None, enabled=True, revision=''):
 require_admin()
 if app_id:
  if not app_id.startswith('company:'): frappe.throw(_('Invalid company app.'))
  doc=frappe.get_doc(APPS,app_id[8:])
  if str(doc.modified)!=revision: frappe.throw(_('This company app changed. Reload before editing.'))
 else: doc=frappe.new_doc(APPS)
 doc.title=clean_text(title,100);doc.url=clean_url(url);doc.category=clean_text(category,60)
 doc.enabled=1 if enabled in (True,1,'1') else 0
 doc.save()
 return get_apps()


def seed_defaults():
 # Stable marker prevents re-adding apps that an administrator has disabled or renamed.
 marker='marloa_work_apps_seeded_v1'
 if frappe.db.get_default(marker): return
 for title,url,category in DEFAULTS:
  if not frappe.db.exists(APPS,{'url':url}):
   frappe.get_doc({'doctype':APPS,'title':title,'url':url,'category':category,'enabled':1}).insert(ignore_permissions=True)
 frappe.db.set_default(marker,'1')
