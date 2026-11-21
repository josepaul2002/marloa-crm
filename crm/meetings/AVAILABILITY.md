# Employee availability and meeting planning

## Employee setup

Profile menu → My availability (also Settings → My availability). Save a timezone,
weekly windows separately for Online and In person, and date-specific replacements.
Empty windows mean unavailable. New employees have unconfigured availability and
are shown as unknown until they save their own preferences. The preset is an
explicit employee action, not an automatic assumption.

Private departure places are owner-only. Employees can opt in to server-side travel
calculations using their default departure point; colleagues receive only the
estimate, never the address. Google Routes receives the origin to compute it.
Managers maintain shared company locations through the Company places link.

## Scheduling

Select meeting type, internal attendees and date range. Assignees are suggested,
not auto-invited. The organizer is initially selected but can be removed when
booking on behalf of others. Optional attendee conflicts do not block required
attendees. External guests are invited but their availability is not checked.

Find a time checks each selected employee's primary calendar and opted-in extra
calendars through the acting user's Google authorization. Missing Google sharing,
API errors and unconfigured working hours are unknown, never free. Slots are
15 minutes apart; search spans at most seven days and ten internal attendees.

In-person checks additionally require a meeting destination and a departure place
or manual travel estimate for each attendee. Driving traffic estimates are for the
checked departure period and are refreshed for the selected slot before sending.
The arrival buffer defaults to 15 minutes. Travel before the meeting is tested
against commitments and visit hours. No live location is collected, and routes
from previous/to following meetings are not inferred. Travel events are not
created on calendars. The origin must reflect the employee's actual departure.

Sending rechecks the selected time. Conflicts/unknown availability require a
manager's explicit reason. Recurring/all-day invitations require manager review
because the checker does not validate every occurrence. No availability check
atomically reserves time against concurrent external calendar changes.

## Access and management

CRM meeting read access follows deal access. Writes require deal write access plus
meeting ownership, assignment or manager role. View-only users cannot write via
generic Frappe APIs; lists are filtered as well as individual document requests.
Only the organizer or a manager with independently granted Google write access
may edit/cancel an invitation. Delegated requests use the manager's OWN token,
never the employee's token. The target calendar must be present in the manager's
Google calendar list. Changes and overrides create audit comments.

## Google setup

Existing Calendar authorization must include Calendar FreeBusy and CalendarList
access. Google Contacts uses the saved per-employee Connected App tokens and
shows a green status icon rather than an unconditional connect button.

Enable Routes API; in Google Settings enter a dedicated server key restricted to
Routes API in `Routes API server key`. Do not use a website-restricted Places key.
`crm.meetings.planning.test_routes_connection` lets a System Manager verify access
with one route between two public Kochi locations. The key is never returned.

## Verification

Pure backend rule tests cover hours, overrides, DST, buffers and unknown status;
mocked permission tests cover manager credential isolation and viewer denial.
Frontend tests mount the installed Frappe Dialog/DatePicker components, verify
persistent connection display, attendee opt-in, invalidation of obsolete results
and separate weekly schedules. Live Google calendar permissions and employee
preferences still determine which real slots can be confirmed.
