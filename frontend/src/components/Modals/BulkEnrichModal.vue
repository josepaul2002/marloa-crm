<template>
  <Dialog v-model:open="show" :options="{ title: __('Enrich organizations'), size: 'xl' }">
    <template #body-content>
      <div class="space-y-4 text-base text-ink-gray-7">
        <p>{{ __('{0} organizations selected', [names.length]) }}</p>
        <p v-if="!started">
          {{ __('Research the selected companies’ websites using your existing enrichment settings. Organizations without a website are skipped. Existing field mapping and overwrite rules still apply. This does not run People Map or find decision makers.') }}
        </p>
        <p v-if="names.length > 25" class="text-ink-red-4" role="alert">
          {{ __('Select up to 25 organizations per batch.') }}
        </p>
        <p v-if="started" aria-live="polite">
          {{ __('{0} completed · {1} failed · {2} skipped', [count('Completed'), count('Failed'), count('Skipped')]) }}
        </p>
        <div v-if="results.length" class="max-h-72 overflow-auto divide-y divide-outline-gray-1 rounded border border-outline-gray-2">
          <div v-for="row in results" :key="row.name" class="flex items-start justify-between gap-4 p-3">
            <span class="break-words">{{ row.name }}</span>
            <span class="shrink-0 text-sm" :class="row.status === 'Failed' ? 'text-ink-red-4' : 'text-ink-gray-6'">{{ __(row.status) }}<span v-if="row.message && !['Queued', 'Completed'].includes(row.status)"> · {{ row.message }}</span></span>
          </div>
        </div>
        <p v-if="started" class="text-sm text-ink-gray-5">
          {{ __('You can close this window. Queued research continues in the background; results appear on each organization and in Enrichment Run history.') }}
        </p>
        <ErrorMessage v-if="error" :message="error" />
      </div>
    </template>
    <template #actions>
      <Button :label="started ? __('Close') : __('Cancel')" @click="show = false" />
      <Button v-if="!started" variant="solid" :label="__('Enrich selected')" :loading="loading" :disabled="!names.length || names.length > 25" @click="start" />
    </template>
  </Dialog>
</template>

<script setup>
import { Dialog, Button, ErrorMessage, call } from 'frappe-ui'
import { ref, onBeforeUnmount } from 'vue'
import { globalStore } from '@/stores/global'
const show = defineModel({ type: Boolean })
const props = defineProps({ names: { type: Array, required: true } })
const emit = defineEmits(['done'])
const results = ref([])
const loading = ref(false)
const started = ref(false)
const error = ref('')
const { $socket } = globalStore()
let timer
let disposed = false
const active = (row) => ['Queued', 'Running'].includes(row.status)
const count = (status) => results.value.filter((row) => row.status === status).length
function progress(event) {
  if (event.reference_doctype !== 'CRM Organization') return
  const row = results.value.find((row) => row.name === event.reference_name)
  if (!row || !active(row)) return
  row.status = event.status === 'completed' ? 'Completed' : event.status === 'error' ? 'Failed' : 'Running'
  row.message = event.message || ''
  if (row.status === 'Completed') emit('done')
}
$socket?.on('domain_enrichment_progress', progress)
async function refresh() {
  for (const row of results.value.filter(active)) {
    if (disposed) return
    try {
      const status = await call('crm.domain_enrichment.api.get_status', { reference_doctype: 'CRM Organization', reference_name: row.name })
      if (!status.running && status.last_run_status) {
        row.status = status.last_run_status
        row.message = (status.notes || []).join(' · ')
        if (row.status === 'Completed') emit('done')
      }
    } catch { /* Realtime remains available; a transient status failure is not a failed run. */ }
  }
  if (!disposed && results.value.some(active)) timer = setTimeout(refresh, 10000)
}
async function start() {
  loading.value = true
  error.value = ''
  try {
    results.value = await call('crm.domain_enrichment.api.bulk_enrich', { names: props.names })
    started.value = true
    timer = setTimeout(refresh, 10000)
  } catch (e) {
    error.value = e.messages?.[0] || e.message || __('Could not start enrichment. Try again.')
  } finally { loading.value = false }
}
onBeforeUnmount(() => {
  disposed = true
  clearTimeout(timer)
  $socket?.off('domain_enrichment_progress', progress)
})
</script>
