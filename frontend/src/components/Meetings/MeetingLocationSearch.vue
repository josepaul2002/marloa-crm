<template>
  <div class="space-y-2">
    <label class="text-sm text-ink-gray-6">{{ __('Search Google Maps') }}</label>
    <div ref="host" />
    <p class="text-xs text-ink-gray-5" role="status">{{ status }}</p>
  </div>
</template>
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
const props = defineProps({ browserKey: String })
const emit = defineEmits(['select'])
const host = ref(null), status = ref('')
let widget, disposed = false, generation = 0
async function choose(event) {
  const id = ++generation
  try {
    const place = event.placePrediction.toPlace()
    await place.fetchFields({ fields: ['displayName', 'formattedAddress'] })
    if (disposed || id !== generation) return
    if (place.formattedAddress) emit('select', place.formattedAddress)
  } catch { status.value = __('Address search unavailable. Enter the address below.') }
}
onMounted(async () => {
  if (!props.browserKey) { status.value = __('Enter the address manually below.'); return }
  try {
    if (!window.google?.maps?.importLibrary) {
      if (!window.__marloaMeetingMaps) window.__marloaMeetingMaps = new Promise((resolve, reject) => {
        const tag = document.createElement('script')
        tag.src = 'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(props.browserKey) + '&loading=async&libraries=places&v=weekly'
        tag.onload = resolve; tag.onerror = reject; tag.async = true; document.head.appendChild(tag)
      })
      await window.__marloaMeetingMaps
    }
    const library = await window.google.maps.importLibrary('places')
    if (disposed) return
    widget = new library.PlaceAutocompleteElement()
    widget.addEventListener('gmp-select', choose)
    host.value.appendChild(widget)
    status.value = __('Choose an address, then review it below.')
  } catch { status.value = __('Address search unavailable. Enter the address below.') }
})
onUnmounted(() => { disposed = true; generation++; widget?.removeEventListener('gmp-select', choose); widget?.remove() })
</script>
