"""Employee-scoped guest suggestions. Google contact data is never bulk-imported."""
import frappe
from crm.api import check_app_permission

PROVIDER = 'Marloa Google Contacts'


def require_crm():
    if frappe.session.user == 'Guest' or not check_app_permission():
        frappe.throw('CRM access required.', frappe.PermissionError)


def contacts_app():
    name=frappe.db.get_value('Connected App',{'provider_name':PROVIDER},'name')
    return frappe.get_doc('Connected App',name) if name else None


@frappe.whitelist()
def authorize_contacts():
    require_crm()
    app=contacts_app()
    if not app:
        frappe.throw('An administrator must configure Marloa Google Contacts first.')
    return {'url':app.initiate_web_application_flow(user=frappe.session.user,
                 success_uri=frappe.utils.get_url('/crm/deals'))}


@frappe.whitelist()
def search_guests(query, deal=None):
    require_crm()
    query=str(query or '').strip()
    if len(query)<2:
        return {'suggestions':[], 'google_status':'not_searched'}
    if len(query)>100:
        frappe.throw('Search text is too long.')
    if deal:
        frappe.get_doc('CRM Deal',deal).check_permission('read')
    rows=frappe.get_list('Contact',or_filters={'full_name':['like',query+'%'],'email_id':['like',query+'%']},
                         fields=['name','full_name','email_id'],limit_page_length=20)
    deal_contacts=set()
    if deal:
        deal_contacts={r.contact for r in frappe.get_doc('CRM Deal',deal).contacts}
    suggestions=[];seen=set()
    for row in rows:
        if row.email_id:
            email=row.email_id.lower()
            if email not in seen:
                suggestions.append({'name':row.full_name,'email':email,'source':'Deal contact' if row.name in deal_contacts else 'CRM contact'})
                seen.add(email)
    suggestions.sort(key=lambda r:r['source']!='Deal contact')
    app=contacts_app()
    status=connection_status()['status']
    if app and status == 'connected':
        try:
            oauth=app.get_oauth2_session(frappe.session.user)
            status='connected'
            for resource,source in [('people:searchContacts','Google contact'),('otherContacts:search','Google other contact')]:
                url='https://people.googleapis.com/v1/'+resource
                # Google requires a warmup search to refresh its search cache.
                warm=oauth.get(url,params={'query':'','readMask':'names,emailAddresses','pageSize':1},timeout=10)
                if warm.status_code in (401,403):
                    status=google_error_status(warm);continue
                warm.raise_for_status()
                response=oauth.get(url,params={'query':query,'readMask':'names,emailAddresses','pageSize':10},timeout=10)
                response.raise_for_status()
                for match in response.json().get('results',[]):
                    person=match.get('person',{})
                    names=person.get('names') or [{}]
                    for address in person.get('emailAddresses',[]):
                        email=address.get('value','').lower()
                        if email and email not in seen:
                            suggestions.append({'name':names[0].get('displayName') or email,'email':email,'source':source});seen.add(email)
        except Exception as error:
            status='reconnect' if type(error).__name__ in ('TokenExpiredError','InvalidGrantError') else 'unavailable'
    return {'suggestions':suggestions[:30],'google_status':status}


@frappe.whitelist()
def configure_contacts_app():
    require_crm()
    frappe.only_for('System Manager')
    app=contacts_app()
    if not app:
        settings=frappe.get_single('Google Settings')
        if not settings.enable or not settings.client_id:
            frappe.throw('Configure Google Settings first.')
        app=frappe.get_doc({'doctype':'Connected App','provider_name':PROVIDER,
            'client_id':settings.client_id,'client_secret':settings.get_password('client_secret'),
            'authorization_uri':'https://accounts.google.com/o/oauth2/v2/auth',
            'token_uri':'https://oauth2.googleapis.com/token',
            'revocation_uri':'https://oauth2.googleapis.com/revoke',
            'scopes':[{'scope':'https://www.googleapis.com/auth/contacts.readonly'},
                      {'scope':'https://www.googleapis.com/auth/contacts.other.readonly'}],
            'query_parameters':[{'key':'access_type','value':'offline'},{'key':'prompt','value':'consent'}]}).insert()
    return {'app':app.name,'redirect_uri':app.redirect_uri,
            'people_api_url':'https://console.cloud.google.com/apis/library/people.googleapis.com'}


def google_error_status(response):
    if response.status_code == 401: return 'reconnect'
    if response.status_code == 403:
        try:
            error = response.json().get('error', {})
            if 'ACCESS_TOKEN_SCOPE_INSUFFICIENT' in str(error) or 'insufficientPermissions' in str(error): return 'reconnect'
        except Exception: pass
        return 'api_unavailable'
    return 'unavailable'


@frappe.whitelist()
def connection_status():
    require_crm()
    app = contacts_app()
    token = app.get_token_cache(frappe.session.user) if app else None
    if not token or not token.get_password('access_token', raise_exception=False):
        return {'status':'not_connected'}
    cache_key = 'marloa-contacts-status:' + frappe.session.user
    cached = frappe.cache.get_value(cache_key)
    if cached: return {'status':cached}
    try:
        oauth = app.get_oauth2_session(frappe.session.user)
        response = oauth.get('https://people.googleapis.com/v1/people:searchContacts',
            params={'query':'','readMask':'names,emailAddresses','pageSize':1},timeout=10)
        status = 'connected' if response.ok else google_error_status(response)
    except Exception as error:
        status = 'reconnect' if type(error).__name__ in ('TokenExpiredError','InvalidGrantError') else 'unavailable'
    frappe.cache.set_value(cache_key,status,expires_in_sec=45)
    return {'status':status}
