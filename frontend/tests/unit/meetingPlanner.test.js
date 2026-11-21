import { createApp, h, nextTick, reactive } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import MeetingPlanner from '../../src/components/Meetings/MeetingPlanner.vue'
const { call } = vi.hoisted(() => ({ call: vi.fn() }))
vi.mock('frappe-ui', async original => ({ ...(await original()), call }))
let app, host
const flush = async () => { await new Promise(r => setTimeout(r, 20)); await nextTick() }
async function mount(data) {
  host = document.createElement('div'); document.body.appendChild(host)
  app = createApp({ render: () => h(MeetingPlanner, { data, deal: 'DEAL-1' }) })
  app.config.globalProperties.__ = globalThis.__; app.mount(host); await flush()
}
afterEach(() => { app?.unmount(); host?.remove(); document.body.innerHTML = ''; vi.clearAllMocks() })
const directory = { me:'me@work.in', people:[{user:'me@work.in',name:'Me'},{user:'assigned@work.in',name:'Assigned',suggested:true}],own_places:[],shared_places:[] }
describe('meeting planning', () => {
 it('suggests assignees without automatically inviting them', async () => {
  call.mockResolvedValue(directory)
  const data=reactive({timezone:'Asia/Kolkata',mode:'Online',internal_attendees:[]})
  await mount(data)
  expect(data.internal_attendees.map(p=>p.user)).toEqual(['me@work.in'])
  expect(host.textContent).toContain('Assigned · Suggested')
 })
 it('requires a physical destination before checking travel, and clears obsolete results', async () => {
  call.mockImplementation(async method => method.endsWith('directory') ? directory : {
   people:[], slots:[], suggestions:[], external_availability:'External guests not checked'
  })
  const data=reactive({timezone:'Asia/Kolkata',mode:'In person',location:'',internal_attendees:[]})
  await mount(data)
  const check=[...host.querySelectorAll('button')].find(b=>b.textContent.includes('Check availability'))
  expect(check.disabled).toBe(true)
  data.location='Company office, Kochi'; await nextTick(); expect(check.disabled).toBe(false)
  check.click(); await flush(); expect(host.textContent).toContain('No confirmed common time')
  data.location='Another office'; await nextTick(); expect(host.textContent).not.toContain('No confirmed common time')
 })
 it('explains a capped visit and renders travel without allowing the slot', async () => {
  const slot={start:'2030-01-01T09:00:00+05:30',end:'2030-01-01T09:30:00+05:30',available:false,people:[{user:'me@work.in',required:true,status:'daily_limit'}],travel:[{user:'me@work.in',before:45,after:0,buffer:15,unknown:false}]}
  call.mockImplementation(async method=>method.endsWith('directory') ? directory : {people:[{user:'me@work.in',name:'Me',timezone:'Asia/Kolkata',configured:true,travel_minutes:45,buffer_minutes:15}],slots:[slot],suggestions:[]})
  await mount(reactive({start:'2030-01-01 09:00:00',timezone:'Asia/Kolkata',mode:'In person',location:'Office',internal_attendees:[]}))
  ;[...host.querySelectorAll('button')].find(b=>b.textContent.includes('Check availability')).click();await flush()
  host.querySelector('button[aria-label*="Daily visit limit"]').click();await nextTick()
  expect(host.textContent).toContain('90 minutes total')
  expect(host.querySelector('[aria-label="Travel and meeting timeline"]')).not.toBeNull()
  expect([...host.querySelectorAll('button')].find(b=>b.textContent.includes('Use this time')).disabled).toBe(true)
 })

})
