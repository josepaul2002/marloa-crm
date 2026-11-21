<template>
  <SettingsLayoutBase :title="__('My availability')" :description="__('Choose when you can attend meetings and customer visits.')">
    <template #content>
      <p v-if="loading" class="text-ink-gray-5">{{ __('Loading your availability…') }}</p>
      <form v-else-if="preferences" class="space-y-6 pb-8" @submit.prevent="save">
        <p v-if="!preferences.configured" class="rounded-lg bg-surface-gray-2 p-3 text-sm text-ink-gray-6">{{ __('Your hours are not set yet. Colleagues will see availability unknown until you save them.') }}</p>
        <FormControl v-model="preferences.timezone" type="select" :options="timezones" :label="__('Your time zone')" />
        <section class="space-y-4">
          <h3 class="text-base font-semibold text-ink-gray-9">{{ __('Weekly hours') }}</h3>
          <div class="flex flex-wrap gap-2"><Button v-for="m in modes" :key="m" :label="__(m)" :variant="mode === m ? 'subtle' : 'ghost'" @click="mode = m" /></div>
          <div class="flex flex-wrap gap-2"><Button :label="__('Start with Monday–Friday, 9–6')" @click="preset" /><Button :label="__('Copy online hours to visits')" @click="copyHours" /></div>
          <div v-for="(day, index) in days" :key="day" class="grid gap-3 border-b border-outline-gray-2 py-3 sm:grid-cols-[110px_1fr]">
            <span class="pt-2 text-sm font-medium text-ink-gray-8">{{ __(day) }}</span>
            <div class="space-y-2">
              <p v-if="!preferences.weekly[mode][index].length" class="text-sm text-ink-gray-5">{{ __('Unavailable') }}</p>
              <div v-for="(window, i) in preferences.weekly[mode][index]" :key="i" class="flex items-center gap-2">
                <TimePicker v-model="window[0]" :aria-label="day + ' start'" /><span class="text-ink-gray-5">–</span><TimePicker v-model="window[1]" :aria-label="day + ' end'" />
                <Button icon="lucide-x" :aria-label="__('Remove time window')" @click="preferences.weekly[mode][index].splice(i, 1)" />
              </div>
              <Button v-if="preferences.weekly[mode][index].length < 4" icon-left="lucide-plus" :label="__('Add hours')" @click="preferences.weekly[mode][index].push(['09:00', '18:00'])" />
            </div>
          </div>
        </section>
        <section class="space-y-4">
          <h3 class="text-base font-semibold text-ink-gray-9">{{ __('Date-specific changes') }}</h3>
          <p class="text-sm text-ink-gray-5">{{ __('These replace the regular hours for that date and meeting type. Leave hours empty to take the day off.') }}</p>
          <div v-for="(row, i) in preferences.exceptions" :key="i" class="space-y-3 rounded-lg border border-outline-gray-2 p-3">
            <div class="grid gap-3 sm:grid-cols-2"><DatePicker v-model="row.date" :label="__('Date')" /><FormControl v-model="row.mode" type="select" :options="modes" :label="__('Meeting type')" /></div>
            <div v-for="(window, j) in row.windows" :key="j" class="flex items-center gap-2"><TimePicker v-model="window[0]" /><span>–</span><TimePicker v-model="window[1]" /><Button icon="lucide-x" :aria-label="__('Remove hours')" @click="row.windows.splice(j,1)" /></div>
            <div class="flex gap-2"><Button v-if="row.windows.length < 4" :label="__('Add hours')" @click="row.windows.push(['09:00','18:00'])" /><Button :label="__('Remove date')" @click="preferences.exceptions.splice(i,1)" /></div>
          </div>
          <Button icon-left="lucide-plus" :label="__('Add date override')" @click="preferences.exceptions.push({ date: '', mode, windows: [] })" />
        </section>
        <section class="space-y-4">
          <h3 class="text-base font-semibold text-ink-gray-9">{{ __('My departure places') }}</h3>
          <p class="text-sm text-ink-gray-5">{{ __('These addresses are private. They are never included in customer invitations.') }}</p>
          <div v-for="(place, i) in preferences.places" :key="place.id" class="space-y-3 rounded-lg border border-outline-gray-2 p-3">
            <FormControl v-model="place.label" :label="__('Place name')" :placeholder="__('Home, office, or another place')" />
            <GoogleAddressField v-model="place.address" :browser-key="browserKey" :label="__('Address')" />
            <Button :label="__('Remove place')" @click="removePlace(i)" />
          </div>
          <Button icon-left="lucide-plus" :label="__('Add private place')" @click="addPlace" />
          <FormControl v-model="preferences.default_place" type="select" :label="__('Usual departure point')" :options="[{ label: __('Choose a place'), value: '' }, ...preferences.places.map(p => ({ label: p.label, value: p.id }))]" />
          <div class="rounded-lg border border-outline-gray-2 p-3"><FormControl v-model="preferences.share_travel_estimate" type="checkbox" :label="__('Allow colleagues to calculate travel from my usual departure point')" /><p class="mt-2 text-sm text-ink-gray-5">{{ __('Colleagues receive a travel estimate, not your private address. The address is sent to Google Maps to calculate the route.') }}</p></div>
          <div class="grid gap-3 sm:grid-cols-2"><FormControl v-model="preferences.travel_mode" type="select" :label="__('Usual travel mode')" :options="travelModes" /><FormControl v-model="preferences.buffer_minutes" type="number" :label="__('Arrival buffer in minutes')" min="0" max="180" /></div>
          <Button v-if="canManagePlaces" :label="__('Manage company places')" @click="managePlaces" />
          <div v-if="sharedPlaces.length" class="text-sm text-ink-gray-6"><h4 class="font-medium">{{ __('Company places') }}</h4><p v-for="p in sharedPlaces" :key="p.name">{{ p.label }} · {{ p.address }}</p></div>
        </section>
        <section class="space-y-3">
          <h3 class="text-base font-semibold text-ink-gray-9">{{ __('Calendars to check') }}</h3>
          <p class="text-sm text-ink-gray-5">{{ __('Your primary work calendar is always checked. Optionally include other calendars. The organizer still needs Google permission to check them.') }}</p>
          <Button :label="__('Load my Google calendars')" :loading="calendarLoading" @click="loadCalendars" />
          <div v-for="calendar in calendars" :key="calendar.id" class="rounded border border-outline-gray-2 p-3"><FormControl :model-value="preferences.calendar_ids.includes(calendar.id)" type="checkbox" :label="calendar.label" @update:model-value="value => toggleCalendar(calendar.id, value)" /></div>
          <p v-if="calendarError" class="text-sm text-ink-gray-5">{{ calendarError }}</p>
        </section>
        <p v-if="error" role="alert" class="text-sm text-ink-red-5">{{ error }}</p>
        <p v-if="saved" role="status" class="text-sm text-ink-green-5">{{ __('Availability saved') }}</p>
        <Button type="submit" variant="solid" :label="__('Save availability')" :loading="saving" />
      </form>
      <p v-else-if="error" role="alert" class="text-ink-red-5">{{ error }}</p>
    </template>
  </SettingsLayoutBase>
</template>
<script setup>
import GoogleAddressField from './GoogleAddressField.vue'
import { ref, onMounted } from 'vue'
import { Button, FormControl, DatePicker, TimePicker, call } from 'frappe-ui'
import SettingsLayoutBase from '@/components/Layouts/SettingsLayoutBase.vue'
const canManagePlaces = ref(false), browserKey = ref('')
const preferences = ref(null), revision = ref(''), sharedPlaces = ref([]), mode = ref('Online')
const loading = ref(true), saving = ref(false), error = ref(''), saved = ref(false), calendars = ref([]), calendarLoading = ref(false), calendarError = ref('')
const modes = ['Online', 'In person'], days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
const timezones = [...new Set(['Asia/Kolkata', 'Australia/Sydney', ...(Intl.supportedValuesOf?.('timeZone') || [])])]
const travelModes = [{ label: __('Driving'), value: 'DRIVE' }, { label: __('Two-wheeler'), value: 'TWO_WHEELER' }, { label: __('Walking'), value: 'WALK' }, { label: __('Public transport'), value: 'TRANSIT' }, { label: __('Cycling'), value: 'BICYCLE' }]
function managePlaces() { window.open('/desk/crm-meeting-place', '_blank', 'noopener,noreferrer') }
function apply(r) { browserKey.value = r.places_browser_key || ''; canManagePlaces.value = Boolean(r.can_manage_places); preferences.value = r.preferences; revision.value = r.revision; sharedPlaces.value = r.places || [] }
onMounted(async () => { try { apply(await call('crm.meetings.preferences.get_preferences')) } catch(e) { error.value = e.message } finally { loading.value = false } })
function addPlace() { preferences.value.places.push({ id: crypto.randomUUID(), label: '', address: '' }) }
function copyHours() { preferences.value.weekly['In person'] = JSON.parse(JSON.stringify(preferences.value.weekly.Online)) }
function preset() { preferences.value.weekly[mode.value] = days.map((_,i) => i < 5 ? [['09:00','18:00']] : []) }
function removePlace(i) { const id = preferences.value.places[i].id; preferences.value.places.splice(i,1); if (preferences.value.default_place === id) preferences.value.default_place = '' }
function toggleCalendar(id, value) { const ids = new Set(preferences.value.calendar_ids); value ? ids.add(id) : ids.delete(id); preferences.value.calendar_ids = [...ids] }
async function loadCalendars() { calendarLoading.value = true; calendarError.value = ''; try { calendars.value = await call('crm.meetings.preferences.list_my_calendars') } catch(e) { calendarError.value = e.message } finally { calendarLoading.value = false } }
async function save() { saving.value = true; error.value = ''; saved.value = false; try { apply(await call('crm.meetings.preferences.save_preferences', { preferences: JSON.stringify(preferences.value), revision: revision.value })); saved.value = true } catch(e) { error.value = e.message } finally { saving.value = false } }
</script>
