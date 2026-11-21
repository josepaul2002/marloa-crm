import { createApp, h, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import MyAvailability from '../../src/components/Meetings/MyAvailability.vue'
const { call } = vi.hoisted(() => ({ call:vi.fn() }))
vi.mock('frappe-ui', async original => ({ ...(await original()),call }))
let app,host
const flush=async()=>{await new Promise(r=>setTimeout(r,20));await nextTick()}
afterEach(()=>{app?.unmount();host?.remove();document.body.innerHTML='';vi.clearAllMocks()})
describe('personal availability settings',()=>{
 it('keeps online and visit hours independent and saves the employee preference',async()=>{
  const preferences={timezone:'Asia/Kolkata',configured:false,weekly:{Online:Array.from({length:7},()=>[]),'In person':Array.from({length:7},()=>[])},exceptions:[],places:[],calendar_ids:[],buffer_minutes:15,travel_mode:'DRIVE',default_place:'',share_travel_estimate:false}
  call.mockImplementation(async method=>method.endsWith('get_preferences')?{preferences,revision:'v1',places:[]}:{preferences,revision:'v2',places:[]})
  host=document.createElement('div');document.body.appendChild(host)
  app=createApp({render:()=>h(MyAvailability)});app.config.globalProperties.__=globalThis.__;app.mount(host);await flush()
  expect(host.textContent).toContain('My availability')
  expect(host.textContent).toContain('Your hours are not set yet')
  const preset=[...host.querySelectorAll('button')].find(b=>b.textContent.includes('Start with Monday'))
  preset.click();await nextTick()
  expect(preferences.weekly.Online[0]).toEqual([['09:00','18:00']])
  expect(preferences.weekly['In person'][0]).toEqual([])
  host.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await flush()
  expect(call).toHaveBeenCalledWith('crm.meetings.preferences.save_preferences',expect.objectContaining({revision:'v1'}))
  const payload=JSON.parse(call.mock.calls.find(([m])=>m.endsWith('save_preferences'))[1].preferences)
  expect(payload.buffer_minutes).toBe(15)
  expect(payload.weekly.Online[5]).toEqual([])
 })
})
