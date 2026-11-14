<template>
  <section class="people-map flex h-full min-h-[600px] flex-col bg-surface-gray-1 text-ink-gray-9">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-outline-gray-2 px-5 py-3">
      <div class="flex items-center gap-2">
        <span class="text-base-medium">People</span>
        <Badge :label="String(people.length)" theme="gray" variant="subtle" />
        <span v-if="dirty" class="text-sm text-ink-gray-5">Unsaved changes</span>
      </div>
      <div class="flex items-center gap-2">
        <Button label="Add person" :iconLeft="PlusIcon" @click="newPerson" />
        <Button label="Save chart" :variant="dirty ? 'solid' : 'subtle'" :disabled="!dirty || busy" :loading="busy" @click="save" />
        <Button label="Research people" :iconLeft="SparklesIcon" :disabled="running || busy" @click="showResearch = !showResearch" />
      </div>
    </div>
    <ErrorMessage v-if="error" :message="error" class="border-b border-outline-gray-2 px-5 py-3" />
    <div v-if="showResearch" class="space-y-4 border-b border-outline-gray-2 px-5 py-4">
      <div class="max-w-lg space-y-4">
        <FormControl v-model="scope" label="Office or country" placeholder="For example, India — Kochi office" :maxlength="200" />
        <Checkbox v-model="usePdl" label="Include People Data Labs" description="Uses its separate allowance. Optional." />
        <p class="text-p-sm text-ink-gray-6">Research uses your Claude credits, with up to five searches per run. Review the results before adding them to your chart.</p>
        <p v-if="!state.configured" class="text-p-sm text-ink-gray-6">Claude is not connected. Add the API key in Marloa People Research Settings to enable research. You can add people manually.</p>
        <Button label="Start research" variant="solid" :disabled="!state.configured || running || busy" @click="research" />
      </div>
    </div>
    <div v-if="running" role="status" class="flex items-center gap-2 border-b border-outline-gray-2 px-5 py-3 text-base text-ink-gray-6">
      <LoaderIcon class="size-4 animate-spin" />
      Research {{ state.research_status.toLowerCase() }}. You can return to this tab later.
    </div>
    <div v-if="state.research_status === 'Ready'" class="border-b border-outline-gray-2 px-5 py-4">
      <details open>
        <summary class="cursor-pointer text-base-medium">Review research draft · {{ state.draft?.length || 0 }} people</summary>
        <p class="my-3 text-p-sm text-ink-gray-6">Choose people to add. Existing reviewed details are preserved.</p>
        <div class="max-h-56 overflow-auto">
          <div v-for="person in state.draft" :key="person.id" class="flex items-start gap-3 border-b border-outline-gray-2 py-3">
            <Checkbox class="mt-1" :model-value="selected.includes(person.id)" :aria-label="`Select ${person.name}`" @update:model-value="setSelected(person.id, $event)" />
            <Avatar :label="person.name" size="lg" />
            <div class="min-w-0 flex-1">
              <div class="text-base-medium">{{ person.name }}</div>
              <div class="mt-1 text-sm text-ink-gray-6">{{ person.title }} · {{ person.department }}</div>
              <p v-if="person.notes" class="mt-1 text-p-sm text-ink-gray-5">{{ person.notes }}</p>
              <div class="mt-2 flex flex-wrap gap-2"><Button v-for="url in person.sources" :key="url" :label="host(url)" :href="url" target="_blank" rel="noopener noreferrer" variant="ghost" size="sm" :iconRight="ExternalLinkIcon" /></div>
            </div>
          </div>
        </div>
        <Button class="mt-3" :label="`Add ${selected.length} selected people`" :disabled="!selected.length" @click="mergeDraft" />
      </details>
    </div>
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-outline-gray-2 px-5 py-2.5">
      <TextInput v-model="query" aria-label="Find a person" placeholder="Find a person or department" class="w-64">
        <template #prefix><SearchIcon class="size-4 text-ink-gray-5" /></template>
      </TextInput>
      <div class="flex items-center gap-4 text-sm text-ink-gray-5">
        <span class="flex items-center gap-1.5"><span class="people-line" />Reviewed</span>
        <span class="flex items-center gap-1.5"><span class="people-line people-line-dashed" />Needs review</span>
        <span v-if="state.researched_at">Updated {{ state.researched_at }}</span>
      </div>
    </div>
    <div class="relative flex min-h-[450px] flex-1">
      <VueFlow :id="flowId" :nodes="graph.nodes" :edges="graph.edges" :nodes-connectable="false" :nodes-draggable="false" :min-zoom="0.15" :max-zoom="1.8" :fit-view-options="{ maxZoom: 1, padding: 0.15 }" fit-view-on-init @nodes-initialized="fitView({ maxZoom: 1, padding: 0.15 })">
        <Background :gap="20" color="var(--surface-gray-4)" :size="2" />
        <Panel position="bottom-center">
          <div class="flex items-center gap-0.5 rounded-[10px] border border-outline-gray-2 bg-surface-gray-1 p-1 shadow-md">
            <Button :icon="MinusIcon" variant="ghost" aria-label="Zoom out" @click="zoomOut({ duration: 150 })" />
            <span class="min-w-11 text-center text-sm text-ink-gray-7">{{ Math.round(viewport.zoom * 100) }}%</span>
            <Button :icon="PlusIcon" variant="ghost" aria-label="Zoom in" @click="zoomIn({ duration: 150 })" />
            <span class="mx-1 h-5 border-l border-outline-gray-2" />
            <Button :icon="MaximizeIcon" variant="ghost" aria-label="Fit chart" @click="fitView()" />
          </div>
        </Panel>
        <template #node-department="{ data }"><span class="text-base-medium text-ink-gray-6">{{ data.label }}</span></template>
        <template #node-person="{ data }">
          <Handle type="target" :position="Position.Top" />
          <article class="people-card w-60 overflow-hidden rounded-[10px] border bg-surface-gray-1 shadow-sm" :class="data.matched || editor?.id === data.id ? 'border-outline-gray-5' : 'border-outline-gray-2'">
            <button class="nodrag flex w-full items-start gap-3 px-3 py-3 text-left hover:bg-surface-gray-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-outline-gray-5" @click="editPerson(data.id)">
              <Avatar :label="data.name" size="lg" />
              <span class="min-w-0 flex-1">
                <span class="block text-base-medium text-ink-gray-9">{{ data.name }}</span>
                <span class="mt-1 block text-sm text-ink-gray-6">{{ data.title || 'Role not specified' }}</span>
                <span class="mt-1 block text-sm text-ink-gray-5">{{ data.department }}</span>
              </span>
            </button>
            <div class="flex items-center justify-between gap-1 border-t border-outline-gray-2 px-2 py-1.5">
              <Button v-if="data.linkedin_url" :href="data.linkedin_url" target="_blank" rel="noopener noreferrer" label="LinkedIn" :iconRight="ExternalLinkIcon" variant="ghost" size="sm" class="nodrag" />
              <span v-else class="px-1 text-sm text-ink-gray-5">No LinkedIn link</span>
              <Button v-if="data.reports" :label="`${data.reports} ${data.reports === 1 ? 'report' : 'reports'}`" :iconLeft="data.collapsed ? ChevronRightIcon : ChevronDownIcon" variant="ghost" size="sm" class="nodrag" @click="toggle(data.id)" />
            </div>
          </article>
          <Handle type="source" :position="Position.Bottom" />
        </template>
        <EmptyState v-if="!people.length" name="people" title="No people added" description="Add a person or research this company to build its organization chart." :icon="UsersIcon" />
      </VueFlow>
      <aside v-if="editor" class="absolute inset-y-0 right-0 z-10 flex w-80 max-w-full flex-col border-l border-outline-gray-2 bg-surface-gray-1">
        <div class="flex h-12 shrink-0 items-center justify-between border-b border-outline-gray-2 px-4">
          <h3 class="text-base-medium">Person details</h3>
          <Button :icon="CloseIcon" variant="ghost" aria-label="Close person details" @click="editor = null" />
        </div>
        <div class="flex-1 overflow-y-auto p-4">
          <form class="space-y-4" @submit.prevent="applyPerson">
            <FormControl v-for="field in editableFields" :key="field.key" v-model="editor[field.key]" :label="field.label" :required="field.key === 'name'" :type="field.key === 'linkedin_url' ? 'url' : 'text'" />
            <FormControl v-model="editor.manager_id" type="select" label="Manager" :options="managerOptions" />
            <FormControl v-if="editor.manager_id" v-model="editor.relationship" type="select" label="Relationship evidence" :options="relationshipOptions" />
            <FormControl v-model="editor.relationship_evidence" type="textarea" label="Supporting evidence" />
            <FormControl v-model="editor.sourceText" type="textarea" label="Source URLs" description="One URL per line" />
            <FormControl v-model="editor.notes" type="textarea" label="Notes" />
            <div class="flex flex-wrap gap-2">
              <Button label="Apply changes" variant="solid" type="submit" />
              <Button v-if="people.some(p => p.id === editor.id)" label="Remove" theme="red" variant="ghost" @click="removePerson" />
            </div>
          </form>
          <div v-if="people.some(p => p.id === editor.id)" class="mt-5 border-t border-outline-gray-2 pt-4">
            <Button :label="editor.contact ? 'Contact already linked' : 'Add to Contacts'" :disabled="dirty || busy || !!editor.contact" :iconLeft="UserPlusIcon" @click="addContact(editor.id)" />
            <p v-if="dirty" class="mt-2 text-p-sm text-ink-gray-6">Save the chart before creating a contact.</p>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount, useId } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { Avatar, Badge, Button, Checkbox, ErrorMessage, FormControl, TextInput, call } from 'frappe-ui'
import EmptyState from '@/components/ListViews/EmptyState.vue'
import { VueFlow, Handle, Panel, Position, useVueFlow } from '@vue-flow/core'
import SearchIcon from '~icons/lucide/search'
import LoaderIcon from '~icons/lucide/loader-circle'
import UsersIcon from '~icons/lucide/users'
import PlusIcon from '~icons/lucide/plus'
import SparklesIcon from '~icons/lucide/sparkles'
import ExternalLinkIcon from '~icons/lucide/external-link'
import MinusIcon from '~icons/lucide/minus'
import MaximizeIcon from '~icons/lucide/maximize'
import CloseIcon from '~icons/lucide/x'
import UserPlusIcon from '~icons/lucide/user-plus'
import ChevronRightIcon from '~icons/lucide/chevron-right'
import ChevronDownIcon from '~icons/lucide/chevron-down'
import { Background } from '@vue-flow/background'
import { chartElements, mergePeople, peopleMapError } from '@/utils/peopleMap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const props = defineProps({ organization: { type: String, required: true } })
const emit = defineEmits(['contacts-changed'])
const prefix = 'crm.api.marloa_people_map.'
const state = ref({}), people = ref([]), dirty = ref(false), busy = ref(false), error = ref('')
const scope = ref(''), usePdl = ref(false), showResearch = ref(false), selected = ref([])
const editor = ref(null), query = ref(''), collapsed = ref(new Set())
const flowId = `people-map-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
const { fitView, zoomIn, zoomOut, viewport } = useVueFlow(flowId)
const graph = computed(() => chartElements(people.value, collapsed.value, query.value))
const running = computed(() => ['Queued', 'Running'].includes(state.value.research_status))
const editableFields = [{ key: 'name', label: 'Name' }, { key: 'title', label: 'Designation' }, { key: 'department', label: 'Department' }, { key: 'linkedin_url', label: 'LinkedIn URL' }]
let timer, disposed = false
function host(url) { try { return new URL(url).hostname } catch { return 'Source' } }
function setSelected(id, checked) { selected.value = checked ? [...new Set([...selected.value, id])] : selected.value.filter(value => value !== id) }
const managerOptions = computed(() => [{ label: 'Unknown / not recorded', value: '' }, ...people.value.filter(p => p.id !== editor.value?.id).map(p => ({ label: p.name, value: p.id }))])
const relationshipOptions = [{ label: 'Unknown (removes line)', value: 'unknown' }, { label: 'Source-backed — needs review', value: 'sourced' }, { label: 'Inferred — not confirmed', value: 'inferred' }, { label: 'Confirmed by me', value: 'confirmed' }]
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
  } catch (e) { error.value = peopleMapError(e) }
}
async function perform(fn) { busy.value = true; error.value = ''; try { await fn() } catch(e) { error.value = peopleMapError(e) } finally { busy.value = false } }
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
.people-map :deep(.vue-flow) {
  --vf-bg-color: var(--surface-gray-1);
  --vf-edge-color: var(--outline-gray-4);
  --vf-node-text: var(--ink-gray-9);
  --vf-handle: var(--outline-gray-4);
  background: var(--surface-gray-1);
}
.people-map :deep(.vue-flow__background) { background-color: var(--surface-gray-1); }
.people-map :deep(.vue-flow__edge-text) { fill: var(--ink-gray-6); font-size: 10px; }
.people-map :deep(.vue-flow__edge-textbg) { fill: var(--surface-gray-1); }
.people-map :deep(.vue-flow__handle) { width: 5px; height: 5px; border: 1px solid var(--surface-gray-1); background: var(--outline-gray-4); }
.people-line { width: 16px; border-top: 1px solid var(--outline-gray-4); }
.people-line-dashed { border-top-style: dashed; }
</style>
