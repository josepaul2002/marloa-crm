<template>
  <section class="space-y-4 rounded-lg border border-outline-gray-2 p-4">
    <div class="flex flex-wrap items-center justify-between gap-2"><h3 class="font-semibold text-ink-gray-9">{{ __('Internal attendees') }}</h3><Button :label="__('My availability')" @click="openPreferences" /></div>
    <p class="text-sm text-ink-gray-5">{{ __('Deal assignees are suggested. Select who needs to attend; viewing a deal does not invite anyone.') }}</p>
    <div class="flex flex-wrap gap-2">
      <Button v-for="person in directory.people" :key="person.user" :variant="selected(person.user) ? 'subtle' : 'outline'" :icon-left="selected(person.user) ? 'lucide-check' : 'lucide-plus'" :label="person.name + (person.suggested ? ' · ' + __('Suggested') : '')" @click="toggle(person)" />
    </div>
    <div v-for="row in data.internal_attendees" :key="row.user" class="space-y-3 rounded-lg bg-surface-gray-2 p-3">
      <div class="flex flex-wrap items-center justify-between gap-3"><span class="text-sm font-medium text-ink-gray-9">{{ employee(row.user)?.name || row.user }}</span><FormControl :model-value="!row.required" type="checkbox" :label="__('Optional attendee')" @update:model-value="v => row.required = !v" /></div>
      <template v-if="data.mode === 'In person'">
        <FormControl v-model="row.origin_source" type="select" :options="originOptions(row)" :label="__('Travelling from')" />
        <FormControl v-if="row.origin_source === 'manual'" v-model="row.origin_address" :label="__('Departure address')" :placeholder="__('Enter a complete address')" />
        <FormControl v-if="row.origin_source === 'personal'" v-model="row.origin_id" type="select" :options="directory.own_places.map(p => ({ label: p.label, value: p.id }))" :label="__('My saved place')" />
        <FormControl v-if="row.origin_source === 'shared'" v-model="row.origin_id" type="select" :options="directory.shared_places.map(p => ({ label: p.label, value: p.name }))" :label="__('Company place')" />
        <div class="grid gap-3 sm:grid-cols-2"><FormControl v-model="row.travel_mode" type="select" :options="travelModes" :label="__('Travel mode')" /><FormControl v-model="row.buffer_minutes" type="number" :label="__('Arrival buffer (minutes)')" min="0" max="180" /></div>
        <FormControl v-model="row.manual_minutes" type="number" :label="__('Manual travel estimate (minutes, optional)')" min="0" max="1440" :placeholder="__('Leave empty to use Google Maps')" />
        <p class="text-xs text-ink-gray-5">{{ __('A colleague’s saved departure address stays private. They must allow travel calculations in My availability, or you can specify an agreed departure place.') }}</p>
      </template>
    </div>
    <div class="border-t border-outline-gray-2 pt-4 space-y-4">
      <h3 class="font-semibold text-ink-gray-9">{{ __('Find a time') }}</h3>
      <p class="text-sm text-ink-gray-5">{{ data.mode === 'In person' ? __('Checks calendars, visit hours, travel time and arrival buffers for the selected destination.') : __('Checks calendar commitments and each employee’s online meeting hours.') }}</p>
      <div class="grid gap-3 sm:grid-cols-3"><DatePicker v-model="from" :label="__('From date')" /><DatePicker v-model="to" :label="__('Through date')" /><FormControl v-model="duration" type="number" :label="__('Duration (minutes)')" min="15" max="480" /></div>
      <Button :label="__('Check availability')" icon-left="lucide-calendar-search" :loading="loading" :disabled="!canCheck" @click="check" />
      <p v-if="!canCheck" class="text-sm text-ink-gray-5">{{ __('Choose dates, required internal attendees and a destination for an in-person meeting first.') }}</p>
      <p v-if="error" role="alert" class="text-sm text-ink-red-5">{{ error }}</p>
      <template v-if="result">
        <div v-for="p in result.people" :key="p.user" class="text-sm text-ink-gray-6">
          <span class="font-medium">{{ p.name }}:</span>
          <span v-if="!p.configured"> {{ __('Availability hours not configured.') }}</span>
          <span v-if="p.calendar_error"> {{ __(p.calendar_error) }}</span>
          <span v-if="data.mode === 'In person'"> {{ p.travel_minutes == null ? __('Travel unavailable') : p.travel_minutes + ' ' + __('minutes travel') + ' + ' + p.buffer_minutes + ' ' + __('minutes buffer') }} · {{ __(p.travel_status) }}</span>
        </div>
        <div class="space-y-2"><h4 class="text-sm font-medium text-ink-gray-9">{{ __('Suggested times') }}</h4><div class="flex flex-wrap gap-2"><Button v-for="slot in result.suggestions" :key="slot.start" :label="format(slot.start) + (slot.optional_conflicts ? ' · ' + slot.optional_conflicts + ' ' + __('optional conflicts') : '')" @click="choose(slot)" /></div><p v-if="!result.suggestions.length" class="text-sm text-ink-gray-5">{{ __('No confirmed common time. Review unavailable calendars, working hours and travel settings.') }}</p></div>
        <div class="overflow-x-auto rounded-lg border border-outline-gray-2">
          <table class="w-full text-left text-sm"><thead class="bg-surface-gray-2"><tr><th class="p-3">{{ __('Time') }} · {{ data.timezone }}</th><th v-for="p in result.people" :key="p.user" class="p-3">{{ p.name }}<span v-if="!p.required" class="block font-normal text-ink-gray-5">{{ __('Optional') }}</span></th></tr></thead>
            <tbody><tr v-for="slot in displayedSlots" :key="slot.start" class="border-t border-outline-gray-2"><td class="whitespace-nowrap p-3"><Button :label="format(slot.start)" variant="ghost" @click="choose(slot)" /></td><td v-for="cell in slot.people" :key="cell.user" class="whitespace-nowrap p-3" :class="statusColor(cell.status)">{{ statusLabel(cell.status) }}</td></tr></tbody>
          </table>
        </div>
        <div class="flex items-center gap-3"><Button :label="__('Previous')" :disabled="page === 0" @click="page--" /><span class="text-sm text-ink-gray-5">{{ page + 1 }} / {{ Math.max(1, Math.ceil(result.slots.length / 24)) }}</span><Button :label="__('Next')" :disabled="(page+1)*24 >= result.slots.length" @click="page++" /></div>
        <p v-if="data.mode === 'In person'" class="text-xs text-ink-gray-5">{{ __('Travel times are estimates for the checked departure period. Travel before the meeting is included in the check. Routes from earlier or to later visits are not inferred; select the actual starting point. Estimates are refreshed for the selected meeting before sending.') }}</p>
        <p class="text-xs text-ink-gray-5">{{ __(result.external_availability) }} {{ __('Selecting a time does not reserve it. Availability is checked again when sending.') }}</p>
      </template>
    </div>
  </section>
</template>
<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Button, FormControl, DatePicker, call } from 'frappe-ui'
const props = defineProps({ data: { type: Object, required: true }, deal: String, meeting: String })
const emit = defineEmits(['selected', 'preferences'])
const directory = ref({ people: [], own_places: [], shared_places: [] }), from = ref(''), to = ref(''), duration = ref(30), result = ref(null), loading = ref(false), error = ref(''), page = ref(0)
let generation = 0, disposed = false
const travelModes = [{ label: __('Driving'), value: 'DRIVE' }, { label: __('Two-wheeler'), value: 'TWO_WHEELER' }, { label: __('Walking'), value: 'WALK' }, { label: __('Public transport'), value: 'TRANSIT' }, { label: __('Cycling'), value: 'BICYCLE' }]
const signature = computed(() => JSON.stringify([props.data.mode, props.data.location, props.data.timezone, props.data.internal_attendees, from.value, to.value, duration.value]))
watch(signature, () => { generation++; result.value = null; page.value = 0 })
const canCheck = computed(() => from.value && to.value && duration.value >= 15 && props.data.internal_attendees.some(p => p.required) && (props.data.mode !== 'In person' || props.data.location?.trim()))
const displayedSlots = computed(() => result.value?.slots.slice(page.value*24, (page.value+1)*24) || [])
onMounted(async () => {
  try {
    directory.value = await call('crm.meetings.preferences.directory', { deal: props.deal })
    const today = new Intl.DateTimeFormat('en-CA', { timeZone: props.data.timezone }).format(new Date())
    from.value = props.data.start?.slice(0,10) || today; to.value = from.value
    if (!props.data.internal_attendees.length) { const me = employee(directory.value.me); if (me) toggle(me) }
  } catch(e) { error.value = e.message }
})
function employee(user) { return directory.value.people.find(p => p.user === user) }
function selected(user) { return props.data.internal_attendees.some(p => p.user === user) }
function toggle(person) {
  const rows = props.data.internal_attendees, index = rows.findIndex(p => p.user === person.user)
  if (index >= 0) rows.splice(index,1)
  else rows.push({ user: person.user, required: true, origin_source: 'default', origin_id: '', origin_address: '', travel_mode: person.travel_mode || 'DRIVE', buffer_minutes: person.buffer_minutes ?? 15, manual_minutes: '' })
}
function originOptions(row) {
  const options = [{ label: __('Employee’s usual departure point'), value: 'default' }, { label: __('Enter an agreed address'), value: 'manual' }]
  if (directory.value.shared_places.length) options.push({ label: __('Company place'), value: 'shared' })
  if (row.user === directory.value.me && directory.value.own_places.length) options.push({ label: __('My saved place'), value: 'personal' })
  return options
}
function openPreferences() { emit('preferences') }
function format(value) { return new Intl.DateTimeFormat(undefined, { timeZone: props.data.timezone, month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }).format(new Date(value)) }
function statusLabel(status) { return ({free:__('Free'),busy:__('Busy'),outside_hours:__('Outside hours'),unknown:__('Unknown'),travel_conflict:__('Travel conflict')})[status] }
function statusColor(status) { return status === 'free' ? 'text-ink-green-5' : status === 'unknown' ? 'text-ink-gray-5' : 'text-ink-orange-5' }
async function check() {
  const id = ++generation; loading.value = true; error.value = ''
  try {
    const next = new Date(to.value+'T00:00:00Z'); next.setUTCDate(next.getUTCDate()+1)
    const response = await call('crm.meetings.planning.find_times', { deal: props.deal, meeting: props.meeting, data: JSON.stringify({ from:from.value+'T00:00:00',to:next.toISOString().slice(0,10)+'T00:00:00',duration:duration.value,timezone:props.data.timezone,mode:props.data.mode,location:props.data.location,attendees:props.data.internal_attendees }) })
    if (!disposed && id === generation) { result.value = response; page.value = 0 }
  } catch(e) { if (id === generation) error.value = e.message } finally { if (id === generation) loading.value = false; else loading.value = false }
}
function localValue(value) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: props.data.timezone, year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit', hourCycle:'h23' }).formatToParts(new Date(value))
  const p = Object.fromEntries(parts.map(v => [v.type, v.value])); return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second}`
}
function choose(slot) { props.data.start = localValue(slot.start); props.data.end = localValue(slot.end); props.data.all_day = false; emit('selected', slot) }
onUnmounted(() => { disposed = true; generation++ })
</script>
