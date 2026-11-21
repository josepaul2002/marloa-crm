import { createApp, h, nextTick, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import GoogleAddressField from '../../src/components/Meetings/GoogleAddressField.vue'
let app,host
const previousGoogle=window.google
const flush=async()=>{await new Promise(r=>setTimeout(r,20));await nextTick()}
afterEach(()=>{app?.unmount();host?.remove();document.body.innerHTML='';window.google=previousGoogle})
async function mount(value,key=''){
 host=document.createElement('div');document.body.appendChild(host)
 app=createApp({render:()=>h(GoogleAddressField,{modelValue:value.value,'onUpdate:modelValue':v=>value.value=v,browserKey:key,label:'Departure address'})})
 app.config.globalProperties.__=globalThis.__;app.mount(host);await flush()
}
describe('compact Google address field',()=>{
 it('uses the selected Google formatted address in the editable field',async()=>{
  let widget
  window.google={maps:{importLibrary:vi.fn().mockResolvedValue({PlaceAutocompleteElement:function(){widget=document.createElement('div');return widget}})}}
  const value=ref('');await mount(value,'browser-test-key')
  const fetchFields=vi.fn().mockResolvedValue(undefined)
  const event=new Event('gmp-select');event.placePrediction={toPlace:()=>({formattedAddress:'Infopark, Kochi, Kerala, India',fetchFields})}
  widget.dispatchEvent(event);await flush()
  expect(value.value).toBe('Infopark, Kochi, Kerala, India')
  expect(fetchFields).toHaveBeenCalledWith({fields:['formattedAddress']})
  expect(host.querySelector('input').value).toBe(value.value)
  expect(host.textContent).not.toContain('Search Google Maps')
 })
 it('allows a manual address when the browser API key is unavailable',async()=>{
  const value=ref('');await mount(value)
  const input=host.querySelector('input');input.value='Agreed departure point';input.dispatchEvent(new Event('input',{bubbles:true}));await nextTick()
  expect(value.value).toBe('Agreed departure point')
 })
})
