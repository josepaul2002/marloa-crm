# Google-connected CRM meetings

The Deal Meetings tab uses the existing Marloa Meeting records. Shared event
fields go to Google; internal summaries, decisions and next actions stay in CRM.
No tasks are created by this integration.

## Activation

1. Deploy/migrate the CRM app. The migration adds opt-in fields and the private
   CRM Calendar Inbox. It leaves calendar imports disabled.
2. As System Manager call `crm.meetings.contacts.configure_contacts_app` once.
   Add its returned redirect URI to the existing Google OAuth web client, keeping
   all Gmail, Calendar and social-login redirects. Enable Google People API.
3. Employees click Connect Google Contacts in scheduling and consent to read-only
   Contacts/Other contacts. Contacts remain employee-scoped and aren't bulk saved.
4. Each employee authorizes a separate Google Calendar connection pointing to a
   dedicated customer calendar. Keep existing primary connections unchanged for
   previously created meetings. Select the dedicated calendar for new bookings.
5. On the dedicated connection confirm customer-calendar use and enable CRM sync.
   Keep framework `pull_from_google_calendar` off: its unfiltered importer is a
   separate mechanism. This worker runs every five minutes.
6. Test on SEPTA: exact Gmail match, unknown guest notification, ambiguous deals,
   time changes, decline/accept, cancellation, repeat instances, Drive links.

Imports use Google calendar + event ID identity and incremental sync tokens.
Unknown meetings are owner-private; employees explicitly choose a deal or ignore.
Exact contact email matching uses existing contact/deal/company links, not domain
inference. Only accessible contacts and deals are candidates. Personal calendars,
resource-only events and special calendar event types aren't imported.

Scheduling uses a persisted deterministic Google event ID before an external
send, and If-Match revision checks for updates/cancellation. Uncertain responses
remain Needs review; reopening checks the existing event before retrying.
Drive links do not copy files or grant guest file access.

Recurring series produce occurrence records on import; their parent scheduling
record remains available internally and is hidden from the list once occurrences
arrive. Complex Google recurrence rules are edited in Google Calendar. Existing
records and notes are preserved. Existing physical-address search uses the
restricted browser key already configured in the legacy meeting script.

## Verification

Frontend unit suite and Vite production build; standalone Python tests:
`test_meeting_matching.py`, `test_meeting_payload.py`,
`test_meeting_sync_guards.py`, `test_meeting_scheduling_guards.py`.
A bench-backed, consented Google test is required before enabling production sync.
