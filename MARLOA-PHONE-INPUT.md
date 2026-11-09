# Contact mobile dialling-code selector

Replaces the separate Mobile phone country control with a dialling-code select directly beside Mobile No in the Contact Quick Entry popup. Also provides the same input for explicit add/edit of Contact mobile numbers in the saved contact sidebar. Other phone controls, leads, emails and customer records retain their existing behaviour.

- Defaults to +91 for an empty new input; can select +61, +971 and all supported phone countries. Country names distinguish territories sharing a calling code.
- Pasting a +country-code or 00-prefixed full number recognises the prefix and places national digits in the number box.
- Uses pinned libphonenumber-js 1.13.15 metadata to handle national trunk prefixes; saves a single international number in Frappe's existing Contact Phone row. Native primary-mobile selection and storage remain in place.
- Partial/invalid new numbers receive a validation message. Existing values are never normalised or rewritten by opening a form. Inline edits remain local until explicit Save; Cancel preserves the original value.
- The migration removes only custom_mobile_country and custom_mobile_phone_country from Contact layouts and hides those legacy custom fields. It does not delete fields, stored values or Contacts. All unrelated configured fields and layout order remain intact.
- Keeps the WhatsApp fields and conditional display already created by the user. Initialises the new Contact checkbox to its intended checked default. A WhatsApp chat button is outside this specific update.
- No third-party lookup, phone-number transmission, API key or subscription is required by the control.

## Validation

Production frontend build, ESLint on changed production files, full upstream frontend suite plus phone component/number parsing tests, isolated mobile layout preservation/idempotence tests. Live inspection of the contact popup and saved-contact edit input remains part of deployment verification.

## Deployment and rollback

Deploy marloa-work-apps on the existing private CRM bench; do not update Framework or Email Delivery Service. Normal migration runs crm.api.marloa_phone.configure_mobile_input. A before snapshot of custom field properties and Contact layouts is retained in the private local outputs/frappe-phone-input folder (not published to GitHub).

Rollback UI/code by redeploying c8681e93d2ddb8477ff4516e711e03385d1a9328. Restore the saved Contact layout and hidden flags only if restoring the legacy separate-country UI is desired. No phone data migration needs reversal.
