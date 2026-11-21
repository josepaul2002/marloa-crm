<template>
  <div class="flex flex-col gap-5 px-5 py-5 sm:px-10">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-xl font-semibold text-ink-gray-9">{{ __('Meetings') }}</h2>
      <div class="flex gap-2">
        <Button :label="__('Record past meeting')" @click="run('_marloaEditMeeting')" />
        <Button variant="solid" icon-left="plus" :label="__('Schedule meeting')" @click="scheduleName = null; scheduling = true" />
      </div>
    </div>
    <div class="flex gap-2">
      <Button v-for="option in ['Upcoming', 'Past', 'All']" :key="option" :variant="filter === option ? 'subtle' : 'ghost'" :label="__(option)" @click="filter = option" />
      <Button icon="refresh-cw" :tooltip="__('Refresh meetings')" :loading="meetings.loading" @click="meetings.reload()" />
    </div>
    <div v-if="inbox.data?.length" class="rounded-lg border border-outline-gray-2 p-4">
      <h3 class="font-medium text-ink-gray-9">{{ __('Meetings needing a deal') }}</h3>
      <div v-for="item in inbox.data" :key="item.name" class="mt-3 flex flex-wrap items-center justify-between gap-2">
        <span class="text-sm text-ink-gray-7">{{ item.title }} · {{ item.starts_at }}</span>
        <div class="flex gap-2"><Button :label="__('Choose deal')" @click="link(item)" /><Button :label="__('Ignore')" @click="ignore(item)" /></div>
      </div>
    </div>
    <div v-if="error" role="alert" class="text-ink-red-5">{{ error }}</div>
    <div v-else-if="meetings.loading && !meetings.data" class="text-ink-gray-5">{{ __('Loading meetings…') }}</div>
    <div v-else-if="!visible.length" class="flex flex-col items-center gap-3 rounded-lg border border-outline-gray-2 py-16 text-ink-gray-5">
      <CalendarIcon class="size-8" />
      <p>{{ __('No meetings in this view') }}</p>
    </div>
    <article v-for="meeting in visible" :key="meeting.name" class="rounded-lg border border-outline-gray-2 bg-surface-cards p-4">
      <div class="flex items-start gap-3">
        <CalendarIcon class="mt-1 size-5 shrink-0 text-ink-gray-6" />
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h3 class="font-medium text-ink-gray-9">{{ meeting.title }}</h3>
            <Badge :label="__(meeting.status)" />
          </div>
          <p class="mt-2 text-sm text-ink-gray-6">{{ formatDate(meeting.meeting_at) }} · {{ __(meeting.mode) }}</p>
          <p class="mt-1 text-sm text-ink-gray-6">{{ meeting.meeting_owner }}</p>
          <p v-if="meeting.attendees" class="mt-1 break-words text-sm text-ink-gray-6">{{ meeting.attendees }}</p>
          <p v-if="meeting.invitation_state === 'Needs review'" class="mt-2 text-sm text-ink-orange-5">{{ __('Google has not confirmed this invitation. Reopen it to check before retrying.') }}</p>
          <p v-if="meeting.response_summary" class="mt-1 text-sm text-ink-gray-6">{{ meeting.response_summary }}</p>
          <div class="mt-3 flex flex-wrap gap-2">
            <Button v-if="safeMeetingLink(meeting.location_or_link) && meeting.status !== 'Cancelled'" :label="__('Open meeting')" icon-left="external-link" @click="openLink(meeting.location_or_link)" />
            <Button :label="__('View details')" @click="selected = selected === meeting.name ? null : meeting.name" />
            <Button v-if="(meeting.calendar_event || meeting.custom_google_event_id) && meeting.status !== 'Cancelled'" :label="__('Edit invitation')" @click="scheduleName = meeting.name; scheduling = true" />
            <Button v-if="(meeting.calendar_event || meeting.custom_google_event_id) && meeting.status !== 'Cancelled'" :label="__('Cancel meeting')" @click="cancel(meeting)" />
          </div>
          <div v-if="selected === meeting.name" class="mt-4 space-y-4 border-t border-outline-gray-2 pt-4">
            <div v-for="field in detailFields" :key="field[0]">
              <template v-if="meeting[field[0]]">
                <h4 class="text-sm font-medium text-ink-gray-9">{{ __(field[1]) }}</h4>
                <p class="mt-1 whitespace-pre-wrap break-words text-sm text-ink-gray-6">{{ meeting[field[0]] }}</p>
              </template>
            </div>
            <Button :label="__('Edit internal notes')" @click="run('_marloaEditMeeting', meeting.name)" />
          </div>
        </div>
      </div>
    </article>
    <ScheduleMeeting v-if="scheduling" v-model="scheduling" :deal="deal" :meeting="scheduleName" @saved="meetings.reload()" />
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { Button, Badge, createResource } from 'frappe-ui'
import ScheduleMeeting from './ScheduleMeeting.vue'
import { renderFieldLayoutDialog } from '@/utils/renderFieldLayoutDialog'
import { call } from 'frappe-ui'
import CalendarIcon from '@/components/Icons/CalendarIcon.vue'
import { meetingIsPast, safeMeetingLink } from '@/utils/meetingWorkspace'
const props = defineProps({ deal: { type: String, required: true }, trigger: { type: Function, required: true } })
const scheduling = ref(false), scheduleName = ref(null)
const filter = ref('Upcoming')
const selected = ref(null)
const error = ref('')
const detailFields = [['location_or_link', 'Location or meeting link'], ['agenda', 'Shared agenda'], ['summary', 'Internal summary'], ['decisions', 'Decisions'], ['next_actions', 'Next actions']]
const meetings = createResource({ url: 'crm.api.marloa_meetings.list_meetings', params: { deal: props.deal }, auto: true, onError: () => { error.value = __('Unable to load meetings. Please retry.') } })
const inbox = createResource({ url: 'crm.api.marloa_meetings.meetings_to_link', auto: true })
const visible = computed(() => (meetings.data || []).filter(m => filter.value === 'All' || (filter.value === 'Past' ? meetingIsPast(m) : !meetingIsPast(m))))
function formatDate(value) { return value ? value + ' (site time)' : __('Time not set') }
function openLink(value) { const url = safeMeetingLink(value); if (url) window.open(url, '_blank', 'noopener,noreferrer') }
async function link(item) {
  await renderFieldLayoutDialog({ title: __('Link calendar meeting'), fields: [{ fieldname: 'deal', label: __('Deal'), fieldtype: 'Link', options: 'CRM Deal', reqd: 1 }], defaults: { deal: props.deal }, onSubmit: async data => {
    await call('crm.api.marloa_meetings.link_calendar_meeting', { name: item.name, deal: data.deal }); await inbox.reload(); await meetings.reload()
  } })
}
async function ignore(item) { try { await call('crm.api.marloa_meetings.link_calendar_meeting', { name: item.name, ignore: 1 }); await inbox.reload() } catch (e) { error.value = e.message } }
async function cancel(meeting) {
  try {
    await renderFieldLayoutDialog({ title: __('Cancel meeting and notify guests'), fields: [{ fieldname: 'confirm', label: __('Notify guests that this meeting is cancelled'), fieldtype: 'Check', reqd: 1 }], onSubmit: async data => {
      if (!data.confirm) return
      const context = await call('crm.meetings.scheduling.scheduling_context', { deal: props.deal, meeting: meeting.name })
      await call('crm.meetings.scheduling.cancel_invitation', { deal: props.deal, meeting: meeting.name, etag: context.event.etag }); await meetings.reload()
    } })
  } catch (e) { error.value = e.message }
}
async function run(method, name) {
  error.value = ''
  try { await props.trigger(method, name); await meetings.reload() }
  catch (e) { error.value = e.message || __('Unable to complete meeting action.') }
}
</script>
