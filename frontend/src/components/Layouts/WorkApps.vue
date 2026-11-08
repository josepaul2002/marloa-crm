<template>
  <div>
    <button type="button" class="flex w-full items-center gap-2 rounded px-2 py-2 text-sm text-ink-gray-7 hover:bg-surface-gray-3" :title="collapsed ? 'Work apps' : undefined" @click="openApps">
      <span class="lucide-grid-2x2 size-4 shrink-0" aria-hidden="true" />
      <span v-if="!collapsed">Work apps</span>
    </button>
    <a v-for="app in favourites" :key="app.id" :href="safeUrl(app.url)" target="_blank" rel="noopener noreferrer" class="flex items-center gap-2 rounded px-2 py-1.5 text-sm text-ink-gray-6 hover:bg-surface-gray-3" :title="app.title + ' (opens in a new tab)'">
      <span class="lucide-external-link size-3.5 shrink-0" aria-hidden="true" />
      <span v-if="!collapsed" class="truncate">{{ app.title }}</span>
    </a>
    <Dialog v-model:open="show" title="Work apps" size="3xl">
      <template #default>
        <p class="mb-3 text-sm text-ink-gray-6">Your work shortcuts. Websites open in a new tab and use their own sign-in.</p>
        <div v-if="error" role="alert" class="mb-3 rounded bg-surface-red-1 p-3 text-sm text-ink-red-4">{{ error }} <button type="button" class="underline" :disabled="busy" @click="load">Reload</button></div>
        <p v-if="loading" role="status">Loading your apps…</p>
        <div class="mb-4 flex flex-wrap items-center gap-3">
          <label class="flex-1 text-sm">Search apps<input v-model="search" type="search" class="mt-1 block w-full rounded border border-outline-gray-2 bg-surface-gray-1 p-2 text-ink-gray-9" /></label>
          <label class="flex items-center gap-2 text-sm"><input v-model="showHidden" type="checkbox" /> Show hidden</label>
          <button type="button" class="rounded border border-outline-gray-2 px-3 py-2 text-sm" :disabled="busy || loading || !loaded" @click="newApp">Add website</button>
        </div>
        <div class="max-h-[45vh] space-y-4 overflow-y-auto">
          <section v-for="group in groups" :key="group.name">
            <h3 class="mb-2 text-sm font-semibold text-ink-gray-7">{{ group.name }}</h3>
            <div class="grid gap-2 sm:grid-cols-2">
              <article v-for="app in group.apps" :key="app.id" class="rounded-lg border border-outline-gray-2 p-3" :class="choice(app).hidden || !app.enabled ? 'opacity-60' : ''">
                <a v-if="app.enabled" :href="safeUrl(app.url)" target="_blank" rel="noopener noreferrer" class="block truncate text-sm font-medium text-ink-gray-9" :title="app.url">{{ app.title }} ↗</a>
                <span v-else class="text-sm font-medium">{{ app.title }} (disabled)</span>
                <p class="mt-1 text-xs text-ink-gray-5">{{ app.id.startsWith('personal:') ? 'Only you' : 'Company app' }}</p>
                <div class="mt-3 flex flex-wrap gap-2 text-xs">
                  <button type="button" class="underline" :disabled="busy" :aria-pressed="!!choice(app).pinned" @click="toggle(app, 'pinned')">{{ choice(app).pinned ? 'Unpin' : 'Pin' }}</button>
                  <button type="button" class="underline" :disabled="busy" @click="toggle(app, 'hidden')">{{ choice(app).hidden ? 'Show' : 'Hide' }}</button>
                  <button type="button" class="underline" :disabled="busy" :aria-label="'Move ' + app.title + ' up'" @click="move(app, -1)">Up</button>
                  <button type="button" class="underline" :disabled="busy" :aria-label="'Move ' + app.title + ' down'" @click="move(app, 1)">Down</button>
                  <button v-if="app.id.startsWith('personal:') || data.can_manage" type="button" class="underline" :disabled="busy" @click="edit(app)">Edit</button>
                </div>
              </article>
            </div>
          </section>
          <p v-if="loaded && !groups.length" class="text-sm text-ink-gray-5">No matching apps. Add a website or show hidden apps.</p>
        </div>
        <form v-if="form" class="mt-4 space-y-3 rounded-lg border border-outline-gray-2 p-4" @submit.prevent="saveForm">
          <h3 class="text-sm font-semibold">{{ form.id ? 'Edit website' : 'Add website' }}</h3>
          <label v-if="data.can_manage && !form.id" class="block text-sm">Who is it for?<select v-model="form.scope" class="ml-2 rounded border border-outline-gray-2 bg-surface-gray-1 p-2"><option value="personal">Only me</option><option value="company">Everyone — company app</option></select></label>
          <p v-else class="text-xs text-ink-gray-5">{{ form.scope === 'company' ? 'Changes apply to everyone.' : 'Only you can see this shortcut.' }}</p>
          <label class="block text-sm">Name<input v-model="form.title" required maxlength="100" class="mt-1 block w-full rounded border border-outline-gray-2 bg-surface-gray-1 p-2" /></label>
          <label class="block text-sm">Website URL<input v-model="form.url" type="url" required placeholder="https://example.com" maxlength="2048" class="mt-1 block w-full rounded border border-outline-gray-2 bg-surface-gray-1 p-2" /></label>
          <label class="block text-sm">Category<input v-model="form.category" required maxlength="60" class="mt-1 block w-full rounded border border-outline-gray-2 bg-surface-gray-1 p-2" /></label>
          <label v-if="form.scope === 'company'" class="flex items-center gap-2 text-sm"><input v-model="form.enabled" type="checkbox" /> Enabled for the company</label>
          <div class="flex gap-3"><button type="submit" :disabled="busy" class="rounded bg-surface-gray-7 px-3 py-2 text-sm text-ink-white">{{ busy ? 'Saving…' : 'Save website' }}</button><button type="button" :disabled="busy" @click="form = null">Cancel</button></div>
        </form>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Dialog, call } from 'frappe-ui'
defineProps({ collapsed: Boolean })
const api = 'crm.api.marloa_work_apps.'
const show = ref(false), loading = ref(false), busy = ref(false), loaded = ref(false)
const error = ref(''), search = ref(''), showHidden = ref(false), form = ref(null)
const data = ref({ company: [], settings: { personal: [], choices: {} }, revision: '', can_manage: false })
const clone = (value) => JSON.parse(JSON.stringify(value))
const choice = (app) => data.value.settings.choices[app.id] || {}
function safeUrl(value) {
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? url.href : undefined } catch { return undefined }
}
const all = computed(() => [...data.value.company, ...data.value.settings.personal.map(a => ({ ...a, enabled: true }))].sort((a,b) => (choice(a).order || 0) - (choice(b).order || 0) || a.title.localeCompare(b.title)))
const favourites = computed(() => all.value.filter(a => a.enabled && choice(a).pinned && !choice(a).hidden && safeUrl(a.url)).slice(0,8))
const groups = computed(() => {
  const result = new Map()
  for (const app of all.value) {
    if ((!app.enabled || choice(app).hidden) && !showHidden.value) continue
    if (!(app.title + ' ' + app.category).toLowerCase().includes(search.value.toLowerCase())) continue
    const name = app.category || 'My apps'
    if (!result.has(name)) result.set(name, [])
    result.get(name).push(app)
  }
  return [...result].map(([name, apps]) => ({ name, apps }))
})
function message(e) { return e?.messages?.join?.(' ') || e?.message || 'Could not save your shortcuts. Please reload and try again.' }
async function load() {
  if (busy.value || loading.value) return
  loading.value = true; error.value = ''
  try { data.value = await call(api + 'get_apps'); loaded.value = true } catch(e) { error.value = message(e) } finally { loading.value = false }
}
async function openApps() { show.value = true; form.value = null; await load() }
async function persist(settings) {
  busy.value = true; error.value = ''
  try { data.value = await call(api + 'save_preferences', { settings: JSON.stringify(settings), revision: data.value.revision }); return true } catch(e) { error.value = message(e); return false } finally { busy.value = false }
}
async function toggle(app, key) {
  const s = clone(data.value.settings)
  s.choices[app.id] = { ...choice(app), [key]: !choice(app)[key] }
  await persist(s)
}
async function move(app, step) {
  const items = all.value.filter(a => a.category === app.category)
  const index = items.findIndex(a => a.id === app.id), target = index + step
  if (target < 0 || target >= items.length) return
  ;[items[index], items[target]] = [items[target], items[index]]
  const s = clone(data.value.settings)
  items.forEach((a,i) => { s.choices[a.id] = { ...choice(a), order: i } })
  await persist(s)
}
function newApp() { form.value = { scope: 'personal', title: '', url: '', category: 'My apps', enabled: true } }
function edit(app) { form.value = { ...app, scope: app.id.startsWith('company:') ? 'company' : 'personal' } }
async function saveForm() {
  if (busy.value) return
  if (!safeUrl(form.value.url)) { error.value = 'Enter an HTTPS website URL without embedded credentials.'; return }
  const f = clone(form.value)
  if (f.scope === 'company') {
    busy.value = true; error.value = ''
    try { data.value = await call(api + 'save_company_app', { title: f.title, url: f.url, category: f.category, app_id: f.id || null, enabled: f.enabled, revision: f.modified || '' }); form.value = null } catch(e) { error.value = message(e) } finally { busy.value = false }
  } else {
    const s = clone(data.value.settings), app = { id: f.id || 'personal:' + crypto.randomUUID(), title: f.title, url: f.url, category: f.category }
    const i = s.personal.findIndex(a => a.id === app.id)
    if (i < 0) s.personal.push(app); else s.personal[i] = app
    if (await persist(s)) form.value = null
  }
}
onMounted(load)
</script>
