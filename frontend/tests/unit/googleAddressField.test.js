import { createApp, h, nextTick, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import GoogleAddressField from '../../src/components/Meetings/GoogleAddressField.vue'
let app,host
const previousGoogle=window.google
const flush=async()=>{await new Promise(r=>setTimeout(r,420));await nextTick()}
afterEach(()=>{app?.unmount();host?.remove();document.body.innerHTML='';window.google=previousGoogle})
async function mount(value,key=''){
 host=document.createElement('div');document.body.appendChild(host)
 app=createApp({render:()=>h(GoogleAddressField,{modelValue:value.value,'onUpdate:modelValue':v=>value.value=v,browserKey:key,label:'Departure address'})})
 app.config.globalProperties.__=globalThis.__;app.mount(host);await nextTick()
}
function input(text){const el=host.querySelector('input');el.value=text;el.dispatchEvent(new Event('input',{bubbles:true}))}
function mockPlaces(fetch){window.google={maps:{importLibrary:vi.fn().mockResolvedValue({AutocompleteSessionToken:class{},AutocompleteSuggestion:{fetchAutocompleteSuggestions:fetch}})}}}
describe('Google address field',()=>{
 it('keeps pasted addresses immediately even when Google rejects quota',async()=>{
  mockPlaces(vi.fn().mockRejectedValue(new Error('Quota exceeded AutocompletePlacesRequest per day')))
  const value=ref('');await mount(value,'browser-test-key');input('Infopark, Kochi, Kerala, India');await nextTick()
  expect(value.value).toBe('Infopark, Kochi, Kerala, India')
  await flush();expect(host.textContent).toContain('reached their limit');expect(host.querySelector('input').value).toBe(value.value)
 })
 it('selects a Google suggestion and retrieves its formatted address',async()=>{
  const fetchFields=vi.fn().mockResolvedValue(undefined)
  mockPlaces(vi.fn().mockResolvedValue({suggestions:[{placePrediction:{placeId:'1',text:{toString:()=> 'Infopark Kochi'},toPlace:()=>({formattedAddress:'Infopark, Kochi, Kerala, India',fetchFields})}}]}))
  const value=ref('');await mount(value,'browser-test-key');input('Infopark Kochi');await flush()
  host.querySelector('[role="option"]').click();await nextTick();await new Promise(r=>setTimeout(r,20))
  expect(value.value).toBe('Infopark, Kochi, Kerala, India');expect(fetchFields).toHaveBeenCalledWith({fields:['formattedAddress']})
 })
 it('allows a manual address when the browser API key is unavailable',async()=>{
  const value=ref('');await mount(value);input('Agreed departure point');await nextTick();expect(value.value).toBe('Agreed departure point')
 })
 it('keeps coordinate entry without spending an autocomplete request',async()=>{
  const fetch=vi.fn();mockPlaces(fetch);const value=ref('');await mount(value,'browser-test-key');input('9.9312, 76.2673');await flush();expect(value.value).toBe('9.9312, 76.2673');expect(fetch).not.toHaveBeenCalled()
 })
})
