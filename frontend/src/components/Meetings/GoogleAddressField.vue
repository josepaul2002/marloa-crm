<template>
  <div class="space-y-2">
    <template v-if="!editing && model">
      <div class="flex items-start gap-2">
        <FormControl v-model="model" class="min-w-0 flex-1" :label="label" :placeholder="__('Full address')" />
        <Button v-if="browserKey" class="mt-5" icon="lucide-map-pin" :aria-label="__('Search or change address on Google Maps')" :tooltip="__('Search Google Maps')" @click="startSearch" />
      </div>
    </template>
    <template v-else-if="browserKey && !manual">
      <label class="block text-sm text-ink-gray-6">{{ label }}</label>
      <div ref="host" class="google-address-field min-h-8 w-full" />
      <p v-if="loading" class="text-xs text-ink-gray-5">{{ __('Loading address search…') }}</p>
      <div class="flex flex-wrap items-center gap-2 text-xs text-ink-gray-5">
        <span v-if="status" role="status">{{ status }}</span>
        <button type="button" class="underline underline-offset-2" @click="manual = true">{{ __('Type address manually') }}</button>
        <button v-if="model" type="button" class="underline underline-offset-2" @click="editing = false">{{ __('Keep saved address') }}</button>
      </div>
    </template>
    <template v-else>
      <FormControl v-model="model" :label="label" :placeholder="__('Full address or latitude, longitude')" />
      <p v-if="status" role="status" class="text-xs text-ink-gray-5">{{ status }}</p>
      <button v-if="browserKey" type="button" class="text-xs text-ink-gray-6 underline underline-offset-2" @click="startSearch">{{ __('Search Google Maps') }}</button>
    </template>
    <details class="text-xs text-ink-gray-5"><summary class="cursor-pointer">{{ __('Use a map pin for an unlisted address') }}</summary><p class="mt-2">{{ __('Open Google Maps, right-click your location and copy its latitude and longitude. Paste the pair as the address, for example 9.9312, 76.2673.') }}</p><FormControl v-model="model" :label="__('Address or coordinates')" /><a href="https://maps.google.com" target="_blank" rel="noopener noreferrer" class="underline">{{ __('Open Google Maps') }}</a></details>
  </div>
</template>
<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { Button, FormControl } from 'frappe-ui'
const props = defineProps({ browserKey: String, label: { type: String, default: 'Address' } })
const model = defineModel({ type: String, default: '' })
const host = ref(null), editing = ref(!model.value), manual = ref(false), loading = ref(false), status = ref('')
let widget, disposed = false, generation = 0
function removeWidget() { widget?.removeEventListener('gmp-select', choose); widget?.remove(); widget = null }
async function choose(event) {
  const id = ++generation
  try {
    const place = event.placePrediction.toPlace()
    await place.fetchFields({ fields: ['formattedAddress'] })
    if (disposed || id !== generation) return
    if (!place.formattedAddress) throw new Error('No formatted address')
    model.value = place.formattedAddress; editing.value = false; removeWidget()
  } catch { if (!disposed) status.value = __('Unable to select that address. Try again or type it manually.') }
}
async function mountSearch() {
  if (!props.browserKey || !editing.value || manual.value || disposed) return
  const id = ++generation; loading.value = true; status.value = ''; removeWidget()
  try {
    if (!window.google?.maps?.importLibrary) {
      if (!window.__marloaMeetingMaps) window.__marloaMeetingMaps = new Promise((resolve,reject) => {
        const tag = document.createElement('script')
        tag.src = 'https://maps.googleapis.com/maps/api/js?key='+encodeURIComponent(props.browserKey)+'&loading=async&libraries=places&v=weekly'
        tag.onload = resolve; tag.onerror = reject; tag.async = true; document.head.appendChild(tag)
      })
      await window.__marloaMeetingMaps
    }
    const library = await window.google.maps.importLibrary('places')
    await nextTick()
    if (disposed || id !== generation || !host.value || !editing.value || manual.value) return
    widget = new library.PlaceAutocompleteElement()
    widget.placeholder = __('Search an address on Google Maps')
    widget.style.width = '100%'; widget.style.borderRadius = '8px'; widget.style.font = 'inherit'
    widget.style.colorScheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'
    widget.addEventListener('gmp-select', choose); host.value.appendChild(widget)
  } catch {
    if (!disposed && id === generation) { status.value = __('Google address search is unavailable. Enter the address manually.'); manual.value = true }
  } finally { if (id === generation) loading.value = false }
}
function startSearch() { editing.value = true; manual.value = false; nextTick(mountSearch) }
watch(() => props.browserKey, () => { if (editing.value) nextTick(mountSearch) })
watch(manual, value => { if (value) { generation++; loading.value = false; removeWidget() } })
onMounted(mountSearch)
onUnmounted(() => { disposed = true; generation++; removeWidget() })
</script>
