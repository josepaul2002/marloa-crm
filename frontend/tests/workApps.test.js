import { createApp, h, nextTick } from 'vue'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
const mock = vi.hoisted(() => ({ call: vi.fn() }))
vi.mock('frappe-ui', () => ({ call: mock.call, Dialog: { props: ['open'], setup(props, { slots }) { return () => props.open ? h('div', slots.default?.()) : null } } }))
import WorkApps from '../src/components/Layouts/WorkApps.vue'
let app, host, state
const flush = async () => { await Promise.resolve(); await nextTick(); await Promise.resolve(); await nextTick() }
function button(text) { return [...host.querySelectorAll('button')].find(b => b.textContent.trim() === text) }
async function click(text) { button(text).click(); await flush() }
beforeEach(async () => {
 state = { company: [{ id: 'company:gmail', title: 'Gmail', url: 'https://mail.google.com/', category: 'Google', enabled: true }], settings: { personal: [], choices: {} }, revision: '', can_manage: false }
 mock.call.mockReset().mockImplementation(async (method,args) => {
  if (method.endsWith('save_preferences')) { state.settings = JSON.parse(args.settings); state.revision = '1' }
  return JSON.parse(JSON.stringify(state))
 })
 host=document.createElement('div');document.body.append(host)
 app=createApp(WorkApps,{collapsed:false});app.mount(host);await flush()
})
afterEach(() => { app.unmount();host.remove() })
test('company links open safely and regular employees cannot choose company scope', async () => {
 await click('Work apps')
 const link=host.querySelector('a')
 expect(link.href).toBe('https://mail.google.com/')
 expect(link.target).toBe('_blank');expect(link.rel).toContain('noopener')
 await click('Add website');expect(host.querySelector('select')).toBeNull()
})
test('pin and hide persist without exposing a user selector', async () => {
 await click('Work apps');await click('Pin')
 expect(state.settings.choices['company:gmail'].pinned).toBe(true)
 expect(host.querySelectorAll('a')).toHaveLength(2)
 expect(mock.call.mock.calls.at(-1)[1]).not.toHaveProperty('user')
 await click('Hide');expect(host.querySelectorAll('a')).toHaveLength(0)
})
test('employee can add a personal website', async () => {
 await click('Work apps');await click('Add website')
 const inputs=host.querySelectorAll('form input')
 for (const [i,value] of ['Research','https://example.com/','My apps'].entries()) { inputs[i].value=value;inputs[i].dispatchEvent(new Event('input',{bubbles:true})) }
 host.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await flush()
 expect(state.settings.personal[0].title).toBe('Research')
 expect(state.settings.personal[0].id).toMatch(/^personal:/)
})
test('dangerous URL is never rendered as a usable link', async () => {
 state.company[0].url='javascript:alert(1)';await click('Work apps')
 expect(host.querySelector('a').hasAttribute('href')).toBe(false)
})
test('save failure retains last successful settings and shows error', async () => {
 await click('Work apps');mock.call.mockRejectedValueOnce(new Error('Reload required'));await click('Pin')
 expect(host.querySelector('[role="alert"]').textContent).toContain('Reload required')
 expect(host.querySelectorAll('a')).toHaveLength(1)
})
