# Marloa organization people map

## What is implemented

Organization → Org Chart. Interactive chart with pan, zoom, fit, search highlighting,
collapse/expand, editable people, manager links, LinkedIn links, source URLs and notes.
No sample people are shipped or inserted in production. Initials are used instead of
unverified photos. Existing website enrichment and company fields are unchanged.

Claude research runs in the background and produces a draft, separate from the saved
chart. Select draft people, merge, review, then save. Matching names/roles or identical
LinkedIn URLs preserve the saved person rather than replacing manually reviewed data.
Unknown manager relationships remain disconnected. Source-backed research is a claim,
not human confirmation: dashed line until a reviewer explicitly confirms it. Source URL
validation checks that URLs were returned by the provider; it does not independently
prove the contents or current employment. All output still needs human review.

Create contacts only from the saved chart. The server checks company write permission,
Contact create permission, linked contact read permission and possible duplicate names
within the company. It never overwrites existing contacts, or creates emails/phones.
LinkedIn and provenance stay in the people map; the generated contact is linked back to
that card. Name duplicates require manual review rather than automatic merging.

## Installation and credentials

1. Deploy this CRM change to the private bench, then update/migrate the site. Both new
   DocTypes must exist before the new tab is used. Back up the site first.
2. System Manager opens `/desk/marloa-people-research-settings`.
3. Enter Anthropic API key directly into the Password field. Select a model ID supported
   by the account with basic web search (`web_search_20250305`). Default: claude-sonnet-4-6.
4. Save. Optionally add a People Data Labs API key; do not enable that lookup otherwise.
5. Set the daily run limit (default 20; server clamps it between 1 and 200).
6. Open an organization with a website, Org Chart → Research people. Enter the local
   office/country scope explicitly, especially for multinational companies.

Existing deployments may alternatively use server environment/site config values
`marloa_anthropic_api_key`, `marloa_people_model`, `marloa_pdl_api_key` (environment
names uppercase). These take precedence. Never put secrets in frontend scripts or Git.
Only System Manager can read/write the raw storage/settings DocTypes. The custom APIs
gate access by the current organization permissions. System Managers retain admin access.

## Credit and data boundaries

Each requested run: one Claude Messages request, max 5 searches, max 6,500 output tokens.
Optional PDL query: up to 10 returned profiles; its separate credits/access rules apply.
No automatic provider top-ups, retries, scheduled refresh, phone/email reveal, direct
LinkedIn scraping or paid fallback providers. A run may still cost credits when it fails.
Reopening saved data does not call providers. There is no fixed retry delay after a run
finishes or fails. Duplicate queued/running jobs are blocked. A site-wide daily Redis
counter remains in place; new runs count even when they fail.
Usage metadata from Claude and PDL profile counts are stored; this is not a dollar bill.
PDL defaults to off. Respect provider retention/license terms before enabling ongoing use.

Only company name, public website, explicitly entered office scope and optional PDL
professional-profile candidates are sent to Claude. Deals, contracts, private CRM notes,
contacts' phones/emails and internal conversation records are not sent.

## Recovery and limitations

Worker timeout is 240 seconds. If a worker dies without writing a result, a System Manager
can set research_status to Failed on the Marloa People Map record; saved chart data is
separate. No live research is verified until credentials and actual provider access are tested.
The first version is on the desktop Organization page; the separate mobile organization
route is not extended. No automatic linking to deals, public chart exports or photos yet.

## Validation

- Python pure validation and mocked API contract tests cover access control, stale writes,
  contact-link injection, duplicates, cycle detection, unsafe LinkedIn links and research
  claims. These do not substitute for a real Frappe database migration/permission test.
- Frontend unit suite plus production Vite build.
- Isolated browser preview uses labelled sample data; manual add/save, person editor,
  missing-credentials notice and console errors checked without customer-record writes.

Live acceptance: verify admin/ordinary employee permissions, settings encryption, two
simultaneous editors, worker completion, real researched sources, optional PDL access and
repeated contact creation. Review Fragomen global vs India scope, Synthite, and a small
clinic with sparse data. Back up/redeploy previous CRM commit for rollback; retain the
new tables for recovery. Do not delete customer data as part of rollback.

## Native CRM appearance

Uses frappe-ui Avatar, Badge, Button, Checkbox, ErrorMessage, FormControl and TextInput,
with Lucide component icons, Frappe typography and semantic theme tokens. Canvas controls
match the CRM workflow editor. Light and dark theme previews use real frappe-ui components
with mocked sample data, not substitute controls. IDs are generated with Vue useId so
organization names with spaces do not break SVG background patterns.
