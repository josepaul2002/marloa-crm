<template>
  <div class="relative space-y-2">
    <FormControl v-model="model" :label="label" :placeholder="__('Paste a full address, search a place, or enter coordinates')" role="combobox" :aria-expanded="Boolean(suggestions.length)" :aria-controls="listId" :aria-activedescendant="suggestions.length ? listId + '-' + active : undefined" autocomplete="off" @update:model-value="search" @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)" @keydown.enter.prevent="selectActive" @keydown.esc="dismiss" />
    <div v-if="suggestions.length" :id="listId" role="listbox" class="absolute left-0 right-0 z-20 max-h-64 overflow-auto rounded-lg border border-outline-gray-2 bg-surface-elevation-1 shadow-lg">
      <button v-for="(prediction, index) in suggestions" :id="listId + '-' + index" :key="prediction.placeId || index" type="button" role="option" :aria-selected="index === active" class="block w-full px-3 py-2 text-left text-sm text-ink-gray-9 hover:bg-surface-gray-2" :class="index === active ? 'bg-surface-gray-2' : ''" @mousedown.prevent @click="choose(prediction)">{{ prediction.text.toString() }}</button>
      <div class="flex items-center justify-end gap-1 border-t border-outline-gray-2 px-3 py-2 text-xs text-ink-gray-5"><img :src="googleMapsLogo" alt="Google Maps" class="size-4 object-contain" />Google Maps</div>
    </div>
    <p v-if="loading" class="text-xs text-ink-gray-5" role="status">{{ __('Searching Google Maps…') }}</p>
    <p v-if="status" class="text-xs text-ink-gray-5" role="status">{{ status }}</p>
    <details class="text-xs text-ink-gray-5"><summary class="cursor-pointer">{{ __('Use a map pin for an unlisted address') }}</summary><p class="mt-2">{{ __('Open Google Maps, right-click your location and copy its latitude and longitude. Paste the pair as the address, for example 9.9312, 76.2673.') }}</p><a href="https://maps.google.com" target="_blank" rel="noopener noreferrer" class="underline">{{ __('Open Google Maps') }}</a></details>
  </div>
</template>
<script setup>
import { ref, shallowRef, onUnmounted } from 'vue'
import { FormControl } from 'frappe-ui'
import googleMapsLogo from '@/assets/integrations/google-maps.svg'
const props = defineProps({ browserKey: String, label: { type: String, default: 'Address' } })
const model = defineModel({ type: String, default: '' })
const emit = defineEmits(['health'])
const suggestions = shallowRef([]), active = ref(0), loading = ref(false), status = ref('')
const listId = 'google-address-' + crypto.randomUUID()
let timer, generation = 0, disposed = false, library, token
async function places() {
  if (library) return library
  if (!window.google?.maps?.importLibrary) {
    if (!window.__marloaMeetingMaps) window.__marloaMeetingMaps = new Promise((resolve, reject) => {
      const tag = document.createElement('script')
      tag.src = 'https://maps.googleapis.com/maps/api/js?key='+encodeURIComponent(props.browserKey)+'&loading=async&libraries=places&v=weekly'
      tag.async = true; tag.onload = resolve; tag.onerror = () => { window.__marloaMeetingMaps = null; tag.remove(); reject(new Error('Maps unavailable')) }; document.head.appendChild(tag)
    })
    await window.__marloaMeetingMaps
  }
  library = await window.google.maps.importLibrary('places')
  return library
}
function dismiss() { generation++; clearTimeout(timer); suggestions.value = []; loading.value = false }
function move(delta) { if (suggestions.value.length) active.value = (active.value + delta + suggestions.value.length) % suggestions.value.length }
function selectActive() { if (suggestions.value[active.value]) choose(suggestions.value[active.value]) }
function search(value) {
  const id = ++generation; clearTimeout(timer); suggestions.value = []; status.value = ''; loading.value = false
  const input = String(value ?? model.value).trim()
  if (!props.browserKey || input.length < 3 || /^\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*$/.test(input)) return
  timer = setTimeout(async () => {
    loading.value = true; emit('health', 'checking')
    try {
      const lib = await places()
      token ||= new lib.AutocompleteSessionToken()
      const response = await lib.AutocompleteSuggestion.fetchAutocompleteSuggestions({ input, sessionToken:token })
      if (disposed || id !== generation) return
      suggestions.value = response.suggestions.map(s => s.placePrediction).filter(Boolean); active.value = 0
      status.value = suggestions.value.length ? '' : __('No Google matches. You can keep the full address you entered.')
      emit('health', 'connected')
    } catch(e) {
      if (disposed || id !== generation) return
      status.value = /quota|429|resource.exhausted/i.test(e?.message || '') ? __('Google address suggestions have reached their limit. Your address is kept; you can continue using the full address or coordinates.') : __('Google suggestions are unavailable. Your address is kept; you can continue using the full address or coordinates.')
      emit('health','error')
    } finally { if (!disposed && id === generation) loading.value = false }
  }, 350)
}
async function choose(prediction) {
  const id = ++generation; clearTimeout(timer); loading.value = true
  try {
    const place = prediction.toPlace(); await place.fetchFields({fields:['formattedAddress']})
    if (disposed || id !== generation) return
    if (!place.formattedAddress) throw new Error('Address unavailable')
    model.value = place.formattedAddress; suggestions.value = []; status.value = ''; token = null; emit('health','connected')
  } catch {
    if (!disposed && id === generation) { status.value = __('Unable to retrieve that suggestion. Your entered address is kept.'); suggestions.value = []; emit('health','error') }
  } finally { if (!disposed && id === generation) loading.value = false }
}
onUnmounted(() => { disposed = true; generation++; clearTimeout(timer) })
</script>
