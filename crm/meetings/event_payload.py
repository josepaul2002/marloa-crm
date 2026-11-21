"""Validated Google event payloads; no OAuth or database dependencies."""
from datetime import datetime, date
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit
import re


def emails(value):
    values = value if isinstance(value,list) else re.split(r'[,;\n]',value or '')
    result=[]
    for value in values:
        value=value.strip().lower()
        if not value:
            continue
        if len(value)>254 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',value):
            raise ValueError('Enter valid guest email addresses.')
        if value not in result:result.append(value)
    return result


def build_payload(data, existing=None):
    existing=existing or {}
    title=str(data.get('title') or '').strip()
    if not title or len(title)>300:raise ValueError('Enter a meeting title of up to 300 characters.')
    zone=data.get('timezone') or 'Asia/Kolkata'
    tz=ZoneInfo(zone)
    all_day=bool(data.get('all_day'))
    if all_day:
        start=date.fromisoformat(str(data['start'])[:10]);end=date.fromisoformat(str(data['end'])[:10])
        start_value={'date':start.isoformat()};end_value={'date':end.isoformat()}
    else:
        start=datetime.fromisoformat(str(data['start']).replace(' ','T'));end=datetime.fromisoformat(str(data['end']).replace(' ','T'))
        if start.tzinfo is None:start=start.replace(tzinfo=tz)
        if end.tzinfo is None:end=end.replace(tzinfo=tz)
        start_value={'dateTime':start.isoformat(),'timeZone':zone};end_value={'dateTime':end.isoformat(),'timeZone':zone}
    if end<=start:raise ValueError('End must be later than start; all-day end dates are exclusive.')
    required=emails(data.get('invitees'));optional=emails(data.get('optional_invitees'))
    if not required and not optional:raise ValueError('Add at least one guest.')
    previous={a['email'].lower():a for a in existing.get('attendees',[]) if a.get('email')}
    guests=[]
    for email in required+optional:
        if email in {a['email'] for a in guests}:continue
        guest={'email':email,'optional':email in optional and email not in required}
        if email in previous:guest['responseStatus']=previous[email].get('responseStatus','needsAction')
        guests.append(guest)
    mode=data.get('mode') or 'Online'
    location=str(data.get('location') or '').strip()
    if mode=='In person' and not location:raise ValueError('Enter the physical meeting address.')
    visibility=data.get('visibility') or 'default'
    if visibility not in ('default','private','public'):raise ValueError('Invalid visibility.')
    reminder=int(data.get('reminder',10))
    if reminder < -1 or reminder > 40320:raise ValueError('Reminder must be between zero and four weeks, or disabled.')
    body={'summary':title,'description':str(data.get('agenda') or ''),'location':location if mode=='In person' else '',
          'start':start_value,'end':end_value,'attendees':guests,'visibility':visibility,
          'transparency':'transparent' if data.get('free') else 'opaque',
          'guestsCanModify':bool(data.get('guests_can_edit')),'guestsCanInviteOthers':bool(data.get('guests_can_invite')),
          'guestsCanSeeOtherGuests':bool(data.get('guests_can_see',True)),
          'reminders':{'useDefault':False,'overrides':[] if reminder==-1 else [{'method':'popup','minutes':reminder}]}}
    repeat=data.get('repeat') or 'NONE'
    if repeat not in ('NONE','DAILY','WEEKLY','MONTHLY','YEARLY'):raise ValueError('Invalid repeat frequency.')
    if existing.get('recurringEventId') and repeat!='NONE':raise ValueError('Edit this recurring occurrence without changing the series rule.')
    count=int(data.get('repeat_count') or 12)
    if not 1<=count<=365:raise ValueError('Choose between 1 and 365 occurrences.')
    body['recurrence']=[] if repeat=='NONE' else [f'RRULE:FREQ={repeat};COUNT={count}']
    attachments=[]
    for value in str(data.get('drive_links') or '').splitlines():
        if not value.strip():continue
        url=urlsplit(value.strip())
        if url.scheme!='https' or url.hostname not in ('drive.google.com','docs.google.com') or url.username or url.password:
            raise ValueError('Attachments must be Google Drive or Google Docs HTTPS links.')
        attachments.append({'fileUrl':value.strip()})
    if len(attachments)>25:raise ValueError('Google supports up to 25 event attachments.')
    body['attachments']=attachments
    return body
