<template>
  <Dialog v-model:open="show" :title="meeting ? __('Edit meeting invitation') : __('Schedule meeting')" size="3xl">
    <template #default>
      <div v-if="loading" class="text-ink-gray-5">{{ __('Loading calendar…') }}</div>
      <form v-else class="space-y-4" @submit.prevent="save">
        <FormControl v-model="data.title" :label="__('Meeting title')" required />
        <div class="grid grid-cols-2 gap-4">
          <FormControl v-model="data.calendar" type="select" :options="calendars" :label="__('Organizer calendar')" :disabled="Boolean(event)" />
          <FormControl v-model="data.mode" type="select" :options="['Online', 'In person']" :label="__('Meeting type')" />
          <FormControl v-model="data.start" :type="data.all_day ? 'date' : 'datetime-local'" :label="__('Start')" required />
          <FormControl v-model="data.end" :type="data.all_day ? 'date' : 'datetime-local'" :label="data.all_day ? __('Last day') : __('End')" required />
        </div>
        <FormControl v-model="data.timezone" :label="__('Time zone')" placeholder="Asia/Kolkata" />
        <MeetingLocationSearch v-if="data.mode === 'In person'" :browser-key="placesKey" @select="value => data.location = value" />
        <FormControl v-if="data.mode === 'In person'" v-model="data.location" :label="__('Physical location')" placeholder="Enter the complete address" />
        <FormControl v-model="query" :label="__('Find a guest')" :placeholder="__('Type a name or email…')" @input="search" />
        <div v-if="suggestions.length" class="max-h-40 overflow-auto rounded border border-outline-gray-2">
          <button v-for="guest in suggestions" :key="guest.email" type="button" class="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-surface-gray-2" @click="addGuest(guest)">
            <span class="text-sm text-ink-gray-9">{{ guest.name }} · {{ guest.email }}</span><span class="text-xs text-ink-gray-5">{{ guest.source }}</span>
          </button>
        </div>
        <div class="flex items-center justify-between gap-2 text-sm text-ink-gray-5">
          <span>{{ googleStatus }}</span>
          <Button :label="__('Connect Google Contacts')" @click="connectContacts" />
        </div>
        <FormControl v-model="data.invitees" type="textarea" :label="__('Guest emails (comma separated)')" required />
        <FormControl v-model="data.agenda" type="textarea" :label="__('Agenda shared with guests')" />
        <details class="rounded border border-outline-gray-2 p-3">
          <summary class="cursor-pointer text-sm font-medium text-ink-gray-8">{{ __('More options') }}</summary>
          <div class="mt-4 space-y-4">
            <FormControl v-model="data.all_day" type="checkbox" :label="__('All-day meeting')" />
            <FormControl v-model="data.optional_invitees" type="textarea" :label="__('Optional guest emails')" />
            <div class="grid grid-cols-2 gap-4">
              <FormControl v-model="data.repeat" type="select" :options="repeatOptions" :label="__('Repeat')" :disabled="Boolean(event?.recurringEventId)" />
              <FormControl v-if="data.repeat !== 'NONE'" v-model="data.repeat_count" type="number" :label="__('Number of occurrences')" />
              <FormControl v-model="data.reminder" type="number" :label="__('Reminder minutes before (-1 disables)')" />
              <FormControl v-model="data.visibility" type="select" :options="visibilityOptions" :label="__('Visibility')" />
            </div>
            <FormControl v-model="data.free" type="checkbox" :label="__('Show as available')" />
            <FormControl v-model="data.guests_can_edit" type="checkbox" :label="__('Guests can edit meeting')" />
            <FormControl v-model="data.guests_can_invite" type="checkbox" :label="__('Guests can invite others')" />
            <FormControl v-model="data.guests_can_see" type="checkbox" :label="__('Guests can see other guests')" />
            <FormControl v-model="data.drive_links" type="textarea" :label="__('Drive document links (one per line)')" />
            <p class="text-sm text-ink-gray-5">{{ __('Files stay in Drive. Adding a link does not grant guests permission to open the file.') }}</p>
          </div>
        </details>
        <p v-if="event?.recurringEventId" class="text-sm text-ink-gray-5">{{ __('You are editing this occurrence, not the entire recurring series.') }}</p>
        <p class="text-sm text-ink-gray-5">{{ __('Saving sends an invitation or update to the listed guests. Check the organizer’s availability before sending.') }}</p>
        <p v-if="error" role="alert" class="text-sm text-ink-red-5">{{ error }}</p>
        <Button type="submit" variant="solid" :label="event ? __('Send update to guests') : __('Send invitation')" :loading="saving" :disabled="!data.calendar || saving || !ready" />
      </form>
    </template>
  </Dialog>
</template>
<script setup>
import MeetingLocationSearch from './MeetingLocationSearch.vue'
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { Dialog, Button, FormControl, call } from 'frappe-ui'
const props = defineProps({ deal: String, meeting: String })
const emit = defineEmits(['saved', 'close'])
const show = defineModel({ default: true })
const ready = ref(false)
const loading = ref(true), saving = ref(false), error = ref(''), event = ref(null), calendars = ref([])
const suggestions = ref([]), query = ref(''), googleStatus = ref('')
const placesKey = ref('')
const requestId = crypto.randomUUID()
let timer, generation = 0, disposed = false
const data = reactive({ title: '', calendar: '', mode: 'Online', start: '', end: '', timezone: 'Asia/Kolkata', location: '', invitees: '', optional_invitees: '', agenda: '', all_day: false, repeat: 'NONE', repeat_count: 12, reminder: 10, visibility: 'default', free: false, guests_can_edit: false, guests_can_invite: false, guests_can_see: true, drive_links: '' })
const repeatOptions = [{ label: __('Does not repeat'), value: 'NONE' }, ...['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'].map(value => ({ label: __(value.charAt(0) + value.slice(1).toLowerCase()), value }))]
const visibilityOptions = [{ label: __('Calendar default'), value: 'default' }, { label: __('Private'), value: 'private' }, { label: __('Public'), value: 'public' }]
onMounted(async () => {
  try {
    const context = await call('crm.meetings.scheduling.scheduling_context', { deal: props.deal, meeting: props.meeting })
    placesKey.value = context.places_browser_key || ''
    calendars.value = context.calendars.map(c => c.name)
    data.calendar = context.calendar || calendars.value[0] || ''
    const m = context.meeting
    if (m) Object.assign(data, { title: m.title, start: m.meeting_at?.replace(' ', 'T').slice(0, 16), end: m.ends_at?.replace(' ', 'T').slice(0, 16), mode: m.mode, location: m.location_or_link, invitees: m.attendees, agenda: m.agenda })
    event.value = context.event
    const e = context.event
    if (e) {
      const rule = (e.recurrence || [])[0] || ''
      if (rule && !/^RRULE:FREQ=(DAILY|WEEKLY|MONTHLY|YEARLY);COUNT=\d+$/.test(rule)) throw new Error(__('This recurring series has a custom rule. Edit its schedule in Google Calendar.'))
      Object.assign(data, { start: (e.start.dateTime || e.start.date).slice(0, e.start.date ? 10 : 16), end: (e.end.date ? new Date(Date.parse(e.end.date + 'T00:00:00Z') - 86400000).toISOString().slice(0, 10) : e.end.dateTime.slice(0, 16)), all_day: Boolean(e.start.date), timezone: e.start.timeZone || 'Asia/Kolkata', title: e.summary, agenda: e.description || '', location: e.location || '', mode: e.hangoutLink || e.conferenceData ? 'Online' : 'In person', invitees: (e.attendees || []).filter(a => !a.optional).map(a => a.email).join(', '), optional_invitees: (e.attendees || []).filter(a => a.optional).map(a => a.email).join(', '), visibility: e.visibility || 'default', free: e.transparency === 'transparent', guests_can_edit: Boolean(e.guestsCanModify), guests_can_invite: Boolean(e.guestsCanInviteOthers), guests_can_see: e.guestsCanSeeOtherGuests !== false, drive_links: (e.attachments || []).map(a => a.fileUrl).join('\n'), repeat: rule.match(/FREQ=(\w+)/)?.[1] || 'NONE', repeat_count: Number(rule.match(/COUNT=(\d+)/)?.[1] || 12), reminder: e.reminders?.useDefault ? 10 : (e.reminders?.overrides?.[0]?.minutes ?? -1) })
    }
    ready.value = true
  } catch (e) { error.value = e.message || __('Unable to load calendar.') }
  finally { loading.value = false }
})
function search() {
  clearTimeout(timer); const id = ++generation
  timer = setTimeout(async () => {
    try {
      const result = await call('crm.meetings.contacts.search_guests', { query: query.value, deal: props.deal })
      if (disposed || id !== generation) return
      suggestions.value = result.suggestions
      googleStatus.value = result.google_status === 'connected' ? __('Google Contacts connected') : __('CRM contacts available; connect Google for additional suggestions')
    } catch { if (id === generation) googleStatus.value = __('Contact search unavailable. Enter an email manually.') }
  }, 300)
}
function addGuest(guest) { const emails = new Set(data.invitees.split(',').map(e => e.trim()).filter(Boolean)); emails.add(guest.email); data.invitees = [...emails].join(', '); suggestions.value = []; query.value = ''; generation++ }
async function connectContacts() { try { const result = await call('crm.meetings.contacts.authorize_contacts'); window.location.assign(result.url) } catch (e) { error.value = e.message } }
async function save() {
  if (saving.value) return
  saving.value = true; error.value = ''
  try { await call('crm.meetings.scheduling.save_invitation', { deal: props.deal, meeting: props.meeting, data: JSON.stringify(data), request_id: requestId, etag: event.value?.etag }); emit('saved'); show.value = false }
  catch (e) { error.value = e.message || __('Invitation could not be confirmed. Reopen the meeting before retrying.') }
  finally { saving.value = false }
}
onUnmounted(() => { disposed = true; generation++; clearTimeout(timer) })
</script>
