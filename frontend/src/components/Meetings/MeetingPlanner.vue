<template>
  <section class="grid gap-5 rounded-lg border border-outline-gray-2 p-4 lg:grid-cols-[260px_minmax(0,1fr)]">
    <aside class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2"><h3 class="font-semibold text-ink-gray-9">{{ __('Internal attendees') }}</h3><Button :label="__('My availability')" @click="openPreferences" /></div>
    <p class="text-sm text-ink-gray-5">{{ __('Deal assignees are suggested. Select who needs to attend; viewing a deal does not invite anyone.') }}</p>
    <FormControl v-model="peopleQuery" :placeholder="__('Search employees…')" :label="__('Add people')" />
    <div class="flex flex-wrap gap-2">
      <Button v-for="person in filteredPeople" :key="person.user" :variant="selected(person.user) ? 'subtle' : 'outline'" :icon-left="selected(person.user) ? 'lucide-check' : 'lucide-plus'" :label="person.name + (person.title ? ' · ' + person.title : '') + (person.suggested ? ' · ' + __('Suggested') : '')" @click="toggle(person)" />
    </div>
    <div v-for="row in data.internal_attendees" :key="row.user" class="space-y-3 rounded-lg border border-outline-gray-2 p-3">
      <div class="flex flex-wrap items-center justify-between gap-3"><span class="text-sm font-medium text-ink-gray-9">{{ employee(row.user)?.name || row.user }}</span><FormControl :model-value="!row.required" type="checkbox" :label="__('Optional attendee')" @update:model-value="v => row.required = !v" /></div>
      <template v-if="data.mode === 'In person'">
        <FormControl :model-value="originChoice(row)" type="select" :options="originOptions(row)" :label="__('Travelling from')" @update:model-value="value => setOrigin(row, value)" />
        <GoogleAddressField v-if="row.origin_source === 'manual'" v-model="row.origin_address" :browser-key="browserKey" :label="__('Departure address')" />
        <Button v-if="row.user === directory.me" variant="ghost" icon-left="lucide-map-pin" :label="__('Add or edit my saved places')" @click="openPreferences" />
        <div class="grid gap-3 sm:grid-cols-2"><FormControl v-model="row.travel_mode" type="select" :options="travelModes" :label="__('Travel mode')" /><FormControl v-model="row.buffer_minutes" type="number" :label="__('Arrival buffer (minutes)')" min="0" max="180" /></div>
        <FormControl v-model="row.manual_minutes" type="number" :label="__('Manual travel estimate (minutes, optional)')" min="0" max="1440" :placeholder="__('Leave empty to use Google Maps')" />
        <p class="text-xs text-ink-gray-5">{{ __('A colleague’s saved departure address stays private. They must allow travel calculations in My availability, or you can specify an agreed departure place.') }}</p>
      </template>
    </div>
    </aside>
    <div class="min-w-0 space-y-4">
      <h3 class="font-semibold text-ink-gray-9">{{ __('Find a time') }}</h3>
      <p class="text-sm text-ink-gray-5">{{ data.mode === 'In person' ? __('Checks calendars, visit hours, travel time and arrival buffers for the selected destination.') : __('Checks calendar commitments and each employee’s online meeting hours.') }}</p>
      <div class="grid gap-3 sm:grid-cols-3"><DatePicker v-model="from" :label="__('From date')" /><DatePicker v-model="to" :label="__('Through date')" /><FormControl v-model="duration" type="number" :label="__('Duration (minutes)')" min="15" max="480" /></div>
      <div class="flex flex-wrap gap-2"><Button :label="__('Previous week')" @click="shiftWeek(-7)" /><Button :label="__('Next week')" @click="shiftWeek(7)" /></div>
      <FormControl v-model="showFullDay" type="checkbox" :label="__('Show all 24 hours')" />
      <Button :label="__('Check availability')" icon-left="lucide-calendar-search" :loading="loading" :disabled="!canCheck" @click="check" />
      <p v-if="!canCheck" class="text-sm text-ink-gray-5">{{ __('Choose dates, required internal attendees and a destination for an in-person meeting first.') }}</p>
      <p v-if="error" role="alert" class="text-sm text-ink-red-5">{{ error }}</p>
      <template v-if="result">
        <div v-for="p in result.people" :key="p.user" class="text-sm text-ink-gray-6">
          <span class="font-medium">{{ p.name }} · {{ p.timezone?.replaceAll('_',' ').split('/').reverse().join(' — ') }}:</span><span v-if="p.daily_limit != null"> {{ __('Daily visit limit') }}: {{ p.daily_limit }}</span>
          <span v-if="!p.configured"> {{ __('Availability hours not configured.') }}</span>
          <span v-if="p.calendar_error"> {{ __(p.calendar_error) }}</span>
          <span v-if="data.mode === 'In person'"> {{ p.travel_minutes == null ? __('Travel unavailable') : p.travel_minutes + ' ' + __('minutes travel') + ' + ' + p.buffer_minutes + ' ' + __('minutes buffer') }} · {{ __(p.travel_status) }}</span>
        </div>
        <div class="space-y-2"><h4 class="text-sm font-medium text-ink-gray-9">{{ __('Suggested times') }}</h4><div class="flex flex-wrap gap-2"><Button v-for="slot in result.suggestions" :key="slot.start" :label="format(slot.start) + (slot.optional_conflicts ? ' · ' + slot.optional_conflicts + ' ' + __('optional conflicts') : '')" @click="choose(slot)" /></div><p v-if="!result.suggestions.length" class="text-sm text-ink-gray-5">{{ __('No confirmed common time. Review unavailable calendars, working hours and travel settings.') }}</p></div>
        <div class="max-h-[520px] overflow-auto rounded-lg border border-outline-gray-2" aria-label="Weekly availability">
          <div class="grid min-w-[840px] grid-cols-7 divide-x divide-outline-gray-2">
            <section v-for="day in weekDays" :key="day.date">
              <h4 class="sticky top-0 bg-surface-gray-2 p-3 text-sm font-medium text-ink-gray-9">{{ day.label }}</h4>
              <div class="space-y-1 p-2">
                <button v-for="slot in day.slots" :key="slot.start" type="button" class="w-full rounded px-2 py-1 text-left text-xs focus-visible:ring-2 focus-visible:ring-outline-gray-4" :class="slot.available ? 'bg-surface-gray-2 text-ink-gray-9 hover:bg-surface-gray-3' : 'text-ink-gray-5'" :aria-label="format(slot.start) + ': ' + slot.people.map(c => employee(c.user)?.name + ' ' + statusLabel(c.status)).join(', ')" @click="inspect(slot)">
                  <span class="block font-medium">{{ timeLabel(slot.start) }}</span>
                  <span class="sr-only">{{ slot.available ? __('Available') : __('View conflicts') }}<span class="mt-1 flex gap-1"><span v-for="cell in slot.people" :key="cell.user" class="inline-block size-1.5 rounded-full" :class="cell.status === 'free' ? 'bg-green-500' : cell.status === 'unknown' ? 'bg-gray-400' : 'bg-orange-400'" :title="employee(cell.user)?.name + ': ' + statusLabel(cell.status)" /></span></span>
                </button>
                <p v-if="!day.slots.length" class="p-2 text-xs text-ink-gray-5">{{ __('No future slots') }}</p>
              </div>
            </section>
          </div>
        </div>
        <section v-if="focusedSlot" class="space-y-3 rounded-lg border border-outline-gray-2 p-3" aria-live="polite">
          <h4 class="text-sm font-semibold text-ink-gray-9">{{ format(focusedSlot.start) }}</h4>
          <div v-for="cell in focusedSlot.people" :key="cell.user" class="flex justify-between gap-4 text-sm"><span>{{ employee(cell.user)?.name || cell.user }} · {{ personTime(focusedSlot.start, cell.user) }}{{ cell.required ? '' : ' · ' + __('Optional') }}</span><span :class="statusColor(cell.status)">{{ statusLabel(cell.status) }}</span></div>
          <div v-for="travel in focusedSlot.travel || []" :key="travel.user" class="rounded bg-surface-gray-2 p-3 text-sm text-ink-gray-7"><span class="font-medium">{{ employee(travel.user)?.name }}</span><p>{{ travel.unknown ? __('Travel could not be verified') : travel.before + ' ' + __('min travel before') + ' + ' + travel.buffer + ' ' + __('min arrival buffer') + ' + ' + duration + ' ' + __('min meeting') + (travel.after ? ' + ' + travel.after + ' ' + __('min onward travel') : '') }}</p></div>
          <Button :label="__('Use this time')" :disabled="!focusedSlot.available" @click="choose(focusedSlot)" />
        </section>
        <p v-if="data.mode === 'In person'" class="text-xs text-ink-gray-5">{{ __('Travel before the visit and onward travel to the next appointment are checked when calendar locations are available. Unknown locations remain unverified. Estimates are refreshed before sending.') }}</p>
        <p class="text-xs text-ink-gray-5">{{ __(result.external_availability) }} {{ __('Selecting a time does not reserve it. Availability is checked again when sending.') }}</p>
      </template>
    </div>
  </section>
</template>
<script setup>
import GoogleAddressField from './GoogleAddressField.vue'
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Button, FormControl, DatePicker, call } from 'frappe-ui'
const props = defineProps({ data: { type: Object, required: true }, deal: String, meeting: String, browserKey: String })
const emit = defineEmits(['selected', 'preferences', 'services'])
const directory = ref({ people: [], own_places: [], shared_places: [] }), from = ref(''), to = ref(''), duration = ref(30), result = ref(null), loading = ref(false), error = ref(''), page = ref(0)
const peopleQuery = ref('')
const filteredPeople = computed(() => directory.value.people.filter(p => (p.name + ' ' + (p.title || '') + ' ' + p.user).toLowerCase().includes(peopleQuery.value.toLowerCase())))
const showFullDay = ref(false)
const focusedSlot = ref(null)
let generation = 0, disposed = false, autoTimer
const travelModes = [{ label: __('Driving'), value: 'DRIVE' }, { label: __('Two-wheeler'), value: 'TWO_WHEELER' }, { label: __('Walking'), value: 'WALK' }, { label: __('Public transport'), value: 'TRANSIT' }, { label: __('Cycling'), value: 'BICYCLE' }]
const signature = computed(() => JSON.stringify([props.data.mode, props.data.location, props.data.timezone, props.data.internal_attendees, from.value, to.value, duration.value]))
watch(signature, () => { generation++; result.value = null; focusedSlot.value = null; page.value = 0; clearTimeout(autoTimer); if(canCheck.value) autoTimer = setTimeout(check, 1000) })
const canCheck = computed(() => from.value && to.value && duration.value >= 15 && props.data.internal_attendees.some(p => p.required) && (props.data.mode !== 'In person' || props.data.location?.trim()))
const displayedSlots = computed(() => result.value?.slots.slice(page.value*24, (page.value+1)*24) || [])
onMounted(async () => {
  try {
    directory.value = await call('crm.meetings.preferences.directory', { deal: props.deal })
    const today = new Intl.DateTimeFormat('en-CA', { timeZone: props.data.timezone }).format(new Date())
    const anchor = props.data.start?.slice(0,10) || today
    const weekday = new Date(anchor+'T12:00:00Z').getUTCDay()
    from.value = addDays(anchor, -((weekday+6)%7)); to.value = addDays(from.value, 6)
    if (!props.data.internal_attendees.length) { const me = employee(directory.value.me); if (me) toggle(me) }
  } catch(e) { error.value = e.message }
})
function addDays(value, offset) { const d = new Date(value+'T12:00:00Z'); d.setUTCDate(d.getUTCDate()+offset); return d.toISOString().slice(0,10) }
function shiftWeek(offset) { from.value = addDays(from.value, offset); to.value = addDays(from.value, 6) }
function timeLabel(value) { return new Intl.DateTimeFormat(undefined, { timeZone:props.data.timezone, hour:'numeric', minute:'2-digit', hour12:true }).format(new Date(value)) }
function inspect(slot) { focusedSlot.value = slot }
const weekDays = computed(() => Array.from({length:7}, (_,i) => {
  const date = addDays(from.value, i)
  return {date, label:new Intl.DateTimeFormat(undefined,{weekday:'short',month:'short',day:'numeric',timeZone:'UTC'}).format(new Date(date+'T12:00:00Z')), slots:(result.value?.slots || []).filter(s => { const local=localValue(s.start); const hour=Number(local.slice(11,13)); return local.slice(0,10) === date && (showFullDay.value || (hour>=7 && hour<21)) })}
}))
function personTime(value, user) { const zone=result.value?.people.find(p=>p.user===user)?.timezone || props.data.timezone; return new Intl.DateTimeFormat(undefined,{timeZone:zone,weekday:'short',hour:'numeric',minute:'2-digit',hour12:true}).format(new Date(value)) }
function employee(user) { return directory.value.people.find(p => p.user === user) }
function selected(user) { return props.data.internal_attendees.some(p => p.user === user) }
function toggle(person) {
  const rows = props.data.internal_attendees, index = rows.findIndex(p => p.user === person.user)
  if (index >= 0) rows.splice(index,1)
  else rows.push({ user: person.user, required: true, origin_source: 'default', origin_id: '', origin_address: '', travel_mode: person.travel_mode || 'DRIVE', buffer_minutes: person.buffer_minutes ?? 15, manual_minutes: '' })
}
function originChoice(row) { return ['personal','shared'].includes(row.origin_source) ? row.origin_source+':'+(row.origin_id || '') : (row.origin_source || 'default') }
function setOrigin(row, value) { const [source, ...id] = value.split(':'); row.origin_source = source; row.origin_id = id.join(':') }
function originOptions(row) {
  const own = row.user === directory.value.me
  const usual = own && directory.value.own_places.find(p => p.id === directory.value.default_place)
  const options = [{ label: usual ? __('Usual departure')+': '+usual.label+' — '+usual.address : __('Employee’s usual departure point'), value: 'default' }, { label: __('Search another departure address'), value: 'manual' }]
  for (const p of directory.value.shared_places) options.push({ label: p.label+' — '+p.address, value: 'shared:'+p.name })
  if (own) for (const p of directory.value.own_places) options.push({ label: p.label+' — '+p.address, value: 'personal:'+p.id })
  return options
}

function openPreferences() { emit('preferences') }
function format(value) { return new Intl.DateTimeFormat(undefined, { timeZone: props.data.timezone, month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' }).format(new Date(value)) }
function statusLabel(status) { return ({free:__('Free'),busy:__('Busy'),outside_hours:__('Outside hours'),holiday:__('Observed holiday'),daily_limit:__('Daily visit limit reached'),unknown:__('Unknown'),travel_conflict:__('Travel conflict')})[status] }
function statusColor(status) { return status === 'free' ? 'text-ink-green-5' : status === 'unknown' ? 'text-ink-gray-5' : 'text-ink-orange-5' }
async function check() {
  clearTimeout(autoTimer); const id = ++generation; emit('services',{calendar:'checking',routes:props.data.mode === 'In person' ? 'checking' : 'unused'}); loading.value = true; error.value = ''
  try {
    const next = new Date(to.value+'T00:00:00Z'); next.setUTCDate(next.getUTCDate()+1)
    const response = await call('crm.meetings.planning.find_times', { deal: props.deal, meeting: props.meeting, data: JSON.stringify({ from:from.value+'T00:00:00',to:next.toISOString().slice(0,10)+'T00:00:00',duration:duration.value,timezone:props.data.timezone,mode:props.data.mode,location:props.data.location,attendees:props.data.internal_attendees }) })
    if (!disposed && id === generation) { result.value = response; page.value = 0; emit('services', {calendar:response.people.some(p=>p.calendar_error) ? 'error' : 'connected',routes:response.services?.routes || 'unused'}) }
  } catch(e) { if (id === generation) { error.value = e.message; emit('services',{calendar:'error',routes:'unused'}) } } finally { if (id === generation) loading.value = false; else loading.value = false }
}
function localValue(value) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: props.data.timezone, year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit', hourCycle:'h23' }).formatToParts(new Date(value))
  const p = Object.fromEntries(parts.map(v => [v.type, v.value])); return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second}`
}
function choose(slot) { props.data.start = localValue(slot.start); props.data.end = localValue(slot.end); props.data.all_day = false; emit('selected', slot) }
onUnmounted(() => { disposed = true; clearTimeout(autoTimer); generation++ })
</script>
