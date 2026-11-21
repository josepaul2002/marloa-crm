"""Pure matching rules: never infer a company from a public email domain."""
from email.utils import parseaddr


def normalize_email(value):
    return parseaddr(value or '')[1].strip().lower()


def choose_deal(attendees, contacts, deals, explicit_deal=None):
    """Inputs must already be restricted to records accessible to the calendar owner."""
    accessible = {d['name']: d for d in deals}
    if explicit_deal and explicit_deal in accessible:
        return {'state': 'linked', 'deal': explicit_deal, 'reason': 'explicit'}
    emails = {normalize_email(a) for a in attendees} - {''}
    matches = {c['name'] for c in contacts if emails.intersection(
        normalize_email(e) for e in c.get('emails', []))}
    candidates = []
    for deal in deals:
        if deal.get('closed'):
            continue
        if matches.intersection(deal.get('contacts', [])):
            candidates.append(deal['name'])
    candidates = sorted(set(candidates))
    if len(candidates) == 1:
        return {'state':'linked', 'deal':candidates[0], 'reason':'exact_contact_email'}
    return {'state':'needs_linking', 'deal':None, 'reason':'multiple_deals' if candidates else 'unknown_guest', 'candidates':candidates}


def validate_guest_permissions(options):
    return {key:bool(options.get(key, default)) for key,default in (
        ('guestsCanModify',False), ('guestsCanInviteOthers',False), ('guestsCanSeeOtherGuests',True))}


def google_event_identity(calendar_id, event):
    # Event IDs identify individual recurring exceptions too; titles/times are not keys.
    if not calendar_id or not event.get('id'):
        raise ValueError('Calendar and event ID required')
    return calendar_id + ':' + event['id']
