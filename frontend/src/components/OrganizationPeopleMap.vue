<template>
  <section class="people-map flex h-full min-h-[600px] flex-col bg-surface-gray-1">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b p-4">
      <div>
        <h2 class="text-lg font-semibold text-ink-gray-9">Company people map</h2>
        <p class="mt-1 text-sm text-ink-gray-6">{{ people.length }} people · {{ state.researched_at ? `Last researched ${state.researched_at}` : 'No research yet' }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button label="Add person" iconLeft="lucide-plus" @click="newPerson" />
        <Button :label="dirty ? 'Save chart •' : 'Save chart'" :disabled="!dirty || busy" @click="save" />
        <Button label="Research people" iconLeft="lucide-sparkles" :disabled="running || busy" @click="showResearch = !showResearch" />
      </div>
    </div>
    <div v-if="error" role="alert" class="border-b bg-red-50 p-3 text-sm text-red-800">{{ error }}</div>
    <div v-if="showResearch" class="space-y-3 border-b p-4">
      <p class="text-sm text-ink-gray-7">Research uses your Anthropic balance: at most 5 web searches and 6,500 output tokens per run. Results stay in a draft until you review them. No phone or email enrichment.</p>
      <p v-if="!state.configured" class="text-sm text-amber-700">Claude is not connected yet. An administrator must open Marloa People Research Settings in Desk and add the server credentials. You can still build a chart manually.</p>
      <label class="block text-sm">Office / country to research<input v-model="scope" class="mt-1 w-full rounded border bg-surface-gray-1 p-2" placeholder="For example: India — Kochi office" maxlength="200" /></label>
      <label class="flex gap-2 text-sm"><input v-model="usePdl" type="checkbox" /> Supplement with People Data Labs (up to 10 profiles; uses its separate allowance)</label>
      <Button label="Start research" :disabled="!state.configured || running || busy" @click="research" />
    </div>
    <div v-if="running" role="status" class="border-b p-4 text-sm text-ink-gray-7">Research {{ state.research_status.toLowerCase() }}. You can leave this tab and return; the saved chart stays unchanged.</div>
    <div v-if="state.research_status === 'Ready'" class="border-b p-4">
      <details open>
        <summary class="cursor-pointer font-medium">Review research draft · {{ state.draft?.length || 0 }} people</summary>
        <p class="my-2 text-sm text-ink-gray-6">Select people to merge into your chart. Existing reviewed people are preserved. Review source-backed reporting claims before confirming them.</p>
        <div class="max-h-56 overflow-auto">
          <label v-for="person in state.draft" :key="person.id" class="flex items-start gap-3 border-b py-2 text-sm">
            <input v-model="selected" type="checkbox" :value="person.id" class="mt-1" />
            <span><strong>{{ person.name }}</strong> · {{ person.title }}<br /><span class="text-ink-gray-6">{{ person.department }} · {{ person.notes }}</span>
              <span class="mt-1 flex flex-wrap gap-2"><a v-for="url in person.sources" :key="url" :href="url" target="_blank" rel="noopener noreferrer" class="text-blue-600 underline">{{ host(url) }}</a></span>
            </span>
          </label>
        </div>
        <Button class="mt-3" :label="`Merge ${selected.length} selected people`" :disabled="!selected.length" @click="mergeDraft" />
      </details>
    </div>
    <div class="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2 text-xs text-ink-gray-6">
      <input v-model="query" aria-label="Find a person" placeholder="Find a person or department…" class="w-64 rounded border bg-surface-gray-1 p-2 text-sm" />
      <span>Solid: reviewed relationship · Dashed: source-backed or inferred · No line: manager unknown</span>
    </div>
    <div class="relative flex min-h-[450px] flex-1">
      <VueFlow :id="flowId" :nodes="graph.nodes" :edges="graph.edges" :nodes-connectable="false" :nodes-draggable="false" :min-zoom="0.15" :max-zoom="1.8" fit-view-on-init @nodes-initialized="fitView()">
        <Background :gap="22" color="#94a3b8" :size="1" />
        <Controls />
        <template #node-department="{ data }"><div class="rounded-full border bg-surface-gray-2 px-4 py-2 text-sm font-semibold text-ink-gray-7">{{ data.label }}</div></template>
        <template #node-person="{ data }">
          <Handle type="target" :position="Position.Top" />
          <article class="w-60 rounded-xl border bg-surface-gray-1 p-4 shadow-sm" :class="data.matched ? 'ring-2 ring-blue-500' : ''">
            <button class="nodrag w-full text-left" @click="editPerson(data.id)">
              <div class="mb-2 flex items-center gap-2"><span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-100 font-semibold text-teal-800">{{ initials(data.name) }}</span><strong class="text-sm text-ink-gray-9">{{ data.name }}</strong></div>
              <p class="text-sm text-ink-gray-7">{{ data.title || 'Role not specified' }}</p>
              <p class="mt-1 text-xs text-ink-gray-5">{{ data.department }}</p>
            </button>
            <div class="mt-3 flex items-center justify-between text-xs">
              <a v-if="data.linkedin_url" :href="data.linkedin_url" target="_blank" rel="noopener noreferrer" class="nodrag text-blue-600 underline">LinkedIn ↗</a><span v-else class="text-ink-gray-5">LinkedIn unavailable</span>
              <button v-if="data.reports" class="nodrag text-ink-gray-7" @click="toggle(data.id)">{{ data.collapsed ? '+' : '−' }} {{ data.reports }} reports</button>
            </div>
          </article>
          <Handle type="source" :position="Position.Bottom" />
        </template>
        <div v-if="!people.length" class="pointer-events-none absolute inset-0 flex items-center justify-center p-8">
          <div class="max-w-sm rounded-xl border bg-surface-gray-1 p-6 text-center shadow-sm"><h3 class="font-semibold text-ink-gray-9">Build a clearer picture of this company</h3><p class="mt-2 text-sm text-ink-gray-6">Research public sources or add people yourself. Unknown reporting relationships stay unconnected.</p></div>
        </div>
      </VueFlow>
      <aside v-if="editor" class="absolute inset-y-0 right-0 z-10 w-80 overflow-y-auto border-l bg-surface-gray-1 p-4 shadow-lg">
        <div class="mb-4 flex justify-between"><h3 class="font-semibold">Person details</h3><button aria-label="Close person details" @click="editor = null">✕</button></div>
        <form class="space-y-3" @submit.prevent="applyPerson">
          <label v-for="field in editableFields" :key="field.key" class="block text-sm">{{ field.label }}<input v-model="editor[field.key]" :required="field.key === 'name'" :type="field.key === 'linkedin_url' ? 'url' : 'text'" class="mt-1 w-full rounded border bg-surface-gray-1 p-2" /></label>
          <label class="block text-sm">Manager<select v-model="editor.manager_id" class="mt-1 w-full rounded border bg-surface-gray-1 p-2"><option value="">Unknown / not recorded</option><option v-for="p in people.filter(p => p.id !== editor.id)" :key="p.id" :value="p.id">{{ p.name }}</option></select></label>
          <label v-if="editor.manager_id" class="block text-sm">Relationship evidence<select v-model="editor.relationship" class="mt-1 w-full rounded border bg-surface-gray-1 p-2"><option value="unknown">Unknown (removes line)</option><option value="sourced">Source-backed — needs review</option><option value="inferred">Inferred — not confirmed</option><option value="confirmed">Confirmed by me</option></select></label>
          <label class="block text-sm">Supporting evidence<textarea v-model="editor.relationship_evidence" class="mt-1 w-full rounded border bg-surface-gray-1 p-2" /></label>
          <label class="block text-sm">Source URLs (one per line)<textarea v-model="editor.sourceText" class="mt-1 w-full rounded border bg-surface-gray-1 p-2" /></label>
          <label class="block text-sm">Notes<textarea v-model="editor.notes" class="mt-1 w-full rounded border bg-surface-gray-1 p-2" /></label>
          <Button label="Apply changes" type="submit" />
          <Button v-if="people.some(p => p.id === editor.id)" label="Remove from chart" theme="red" @click="removePerson" />
        </form>
        <div v-if="people.some(p => p.id === editor.id)" class="mt-4 border-t pt-4"><Button :label="editor.contact ? 'Contact already linked' : 'Add to Frappe Contacts'" :disabled="dirty || busy || !!editor.contact" @click="addContact(editor.id)" /><p v-if="dirty" class="mt-2 text-xs text-ink-gray-6">Save the chart before creating a contact.</p></div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { Button, call } from 'frappe-ui'
import { VueFlow, Handle, Position, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { chartElements, mergePeople } from '@/utils/peopleMap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'

const props = defineProps({ organization: { type: String, required: true } })
const emit = defineEmits(['contacts-changed'])
const prefix = 'crm.api.marloa_people_map.'
const state = ref({}), people = ref([]), dirty = ref(false), busy = ref(false), error = ref('')
const scope = ref(''), usePdl = ref(false), showResearch = ref(false), selected = ref([])
const editor = ref(null), query = ref(''), collapsed = ref(new Set())
const flowId = `people-map-${props.organization}`
const { fitView } = useVueFlow(flowId)
const graph = computed(() => chartElements(people.value, collapsed.value, query.value))
const running = computed(() => ['Queued', 'Running'].includes(state.value.research_status))
const editableFields = [{ key: 'name', label: 'Name' }, { key: 'title', label: 'Designation' }, { key: 'department', label: 'Department' }, { key: 'linkedin_url', label: 'LinkedIn URL' }]
let timer, disposed = false
function host(url) { try { return new URL(url).hostname } catch { return 'Source' } }
function initials(name) { return name.split(' ').map(s => s[0]).slice(0, 2).join('') }
async function load() {
  try {
    const result = await call(prefix + 'get_map', { organization: props.organization })
    if (disposed) return
    // Preserve the revision paired with local edits so a concurrent change is detected on save.
    if (dirty.value) result.revision = state.value.revision
    state.value = result
    if (!dirty.value) people.value = result.people || []
    if (result.research_error) error.value = result.research_error
    if (running.value) timer = setTimeout(load, 4000)
  } catch (e) { error.value = e.message || 'Could not load the people map.' }
}
async function perform(fn) { busy.value = true; error.value = ''; try { await fn() } catch(e) { error.value = e.message || 'Action failed.' } finally { busy.value = false } }
function save() { return perform(async () => { state.value = await call(prefix + 'save_map', { organization: props.organization, people: JSON.stringify(people.value), revision: state.value.revision || 0 }); people.value = state.value.people; dirty.value = false }) }
function research() { return perform(async () => { const result = await call(prefix + 'start_research', { organization: props.organization, scope: scope.value, use_pdl: usePdl.value }); if (dirty.value) result.revision = state.value.revision; state.value = result; showResearch.value = false; clearTimeout(timer); timer = setTimeout(load, 2000) }) }
function mergeDraft() { people.value = mergePeople(people.value, (state.value.draft || []).filter(p => selected.value.includes(p.id))); selected.value = []; dirty.value = true }
function newPerson() { editor.value = { id: crypto.randomUUID(), name: '', title: '', department: '', linkedin_url: '', manager_id: '', relationship: 'unknown', sources: [], sourceText: '', notes: '', relationship_evidence: '' } }
function editPerson(id) { const p = people.value.find(p => p.id === id); editor.value = { ...p, sourceText: (p.sources || []).join('\n') } }
function applyPerson() {
  const p = { ...editor.value, sources: editor.value.sourceText.split('\n').map(s => s.trim()).filter(Boolean) }
  delete p.sourceText
  if (p.relationship === 'unknown') p.manager_id = ''
  const byId = new Map(people.value.map(x => [x.id, x])); byId.set(p.id, p)
  let current = p; const seen = new Set()
  while(current) { if(seen.has(current.id)) { error.value = 'A reporting relationship cannot form a cycle.'; return }; seen.add(current.id); current = byId.get(current.manager_id) }
  const index = people.value.findIndex(x => x.id === p.id)
  if (index >= 0) people.value[index] = p; else people.value.push(p)
  dirty.value = true; editor.value = null; error.value = ''
}
function removePerson() { const id = editor.value.id; people.value = people.value.filter(p => p.id !== id).map(p => p.manager_id === id ? { ...p, manager_id: '', relationship: 'unknown' } : p); dirty.value = true; editor.value = null }
function toggle(id) { const next = new Set(collapsed.value); next.has(id) ? next.delete(id) : next.add(id); collapsed.value = next }
function addContact(person_id) { return perform(async () => { await call(prefix + 'add_contact', { organization: props.organization, person_id }); await load(); editor.value = null; emit('contacts-changed') }) }
watch(() => props.organization, () => { clearTimeout(timer); dirty.value = false; editor.value = null; load() }, { immediate: true })
onBeforeRouteLeave(() => !dirty.value || window.confirm('Leave without saving your chart changes?'))
function warnUnsaved(event) { if (dirty.value) { event.preventDefault(); event.returnValue = '' } }
window.addEventListener('beforeunload', warnUnsaved)
onBeforeUnmount(() => { window.removeEventListener('beforeunload', warnUnsaved); disposed = true; clearTimeout(timer) })
</script>

<style scoped>
.people-map :deep(.vue-flow__background) { background-color: var(--surface-gray-2, #f7f9fb); }
.people-map :deep(.vue-flow__node-person article) { border-radius: 12px; border-color: var(--outline-gray-2, #dbe3e9); }
.people-map :deep(.vue-flow__edge-text) { font-size: 10px; }
.people-map input, .people-map select, .people-map textarea { border-radius: 6px; }
</style>
