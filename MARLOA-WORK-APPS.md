# Marloa Work apps

Based on upstream CRM 16.0.2, commit 19786bf. Adds company app tiles and individual website shortcuts to the modern CRM sidebar on desktop and mobile.

Employees can add/edit personal HTTPS websites, pin up to eight favourites to their sidebar, hide/show apps, search and reorder apps within a category. Preferences are saved on the server against the authenticated Frappe user; the client cannot choose another user. System Managers can add/edit/disable company-wide apps. Company apps and private preferences are separate DocTypes. Normal employees have no generic DocType access to either table; the scoped API enforces CRM access, company edit privileges and the current-session preference owner. System Managers retain normal administrative access.

The company defaults include Gmail, Drive, Shared drives, Calendar, Meet, ChatGPT, Claude and four Marloa product/staff destinations, separated into production and development categories. Set the Customer documents company app URL to the actual customer Shared drive after installation; no private folder identifiers or credentials are included in this repository. Meetmind is omitted until a web URL exists.

This is an app launcher, not universal SSO, an iframe embed or data synchronisation. External sites enforce their own access and sign-in. No credentials, OAuth scopes, mail, calendar or Drive permissions are changed. Website names are rendered as escaped text; links use HTTPS and noopener/noreferrer. No favicons are fetched from third parties. Personal settings have optimistic concurrency checks and failed saves preserve the previous state. Disabled company apps are not returned to regular users. Existing CRM customer records, custom scripts and workflows are not overwritten.

## Validation

- Full frontend production build completed using the upstream lockfile and matching Framework UI sources.
- 11 isolated API contract tests: current-user privacy, absence of user selector, denied company editing for regular users, denied Guest/non-CRM access, stale-save handling, URL validation, company disable, duplicate/limit checks and default URL checks.
- 5 Vue rendering/interaction tests: safe external links, company scope unavailable to ordinary users, pin/hide persistence, adding a personal website, dangerous URLs, failed-save handling.
- These are local contract tests and build verification. A real Frappe migration, live browser visual review and two real employee-session checks are still required before calling this deployed and verified.

## Deployment

Use this fork's `marloa-work-apps` branch as the CRM app source on the existing private bench. Keep Framework and Email Delivery Service unchanged. Back up the site, deploy the branch and migrate the site. The normal after_migrate hook creates 11 default company links exactly once. Two new DocTypes are synced by normal Frappe migration. Do not use temporary Cloud App Patches for persistence.

Before deployment, review the specific source/commit and arrange the brief site restart. No secrets need to be entered into the code or shared in chat. If Frappe Cloud asks for GitHub access, restrict it to this repository.

Live checks: expanded/collapsed/mobile sidebar, keyboard access/dialog close, dark/light themes, personal app save/reload, pin/hide/reorder, admin company editing/disable, and two employee sessions verifying personal settings isolation. Verify existing meeting controls, attachments and deal records remain available. Use benign test links; do not send messages or change customers to test this feature.

## Rollback and maintenance

Redeploy the previous official CRM source at commit 19786bf. The two new tables can remain for recovery; do not delete user preference records. Existing customer records are not migrated into these tables. Keep the fork branch pinned and review upstream updates before merging. This code is maintained in Marloa's fork, so future CRM updates need to retain the WorkApps component/API/schema/hook changes.
