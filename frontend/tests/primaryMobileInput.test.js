import { createApp, h, nextTick } from 'vue'
import { afterEach, expect, it, vi } from 'vitest'
vi.mock('frappe-ui', () => {
  const Box = { setup(p,{slots,attrs}) {return () => h('div',attrs,[slots.default?.(),slots.suffix?.()])} }
  return { ErrorMessage: {props:['message'],setup(p){return()=>h('p',p.message)}},ItemListRow:Box,TextInput:Box,Tooltip:Box }
})
import PrimaryDropdownItem from '@/components/PrimaryDropdownItem.vue'
let app,host
const tick=async()=>{await nextTick();await Promise.resolve();await nextTick()}
async function mount(option) {
 host=document.createElement('div');document.body.append(host)
 app=createApp(PrimaryDropdownItem,{phoneInput:true,option})
 app.config.globalProperties.__ = (text) => text
 app.component('Button',{props:['label'],setup(p,{attrs}){return()=>h('button',attrs,p.label||attrs.tooltip)}})
 app.mount(host);await tick()
}
function button(label){return [...host.querySelectorAll('button')].find(b=>b.textContent===label)}
afterEach(()=>{app.unmount();host.remove()})
it('keeps a new mobile in a local draft and saves it only on explicit Save',async()=>{
 const onSave=vi.fn().mockResolvedValue(true)
 await mount({value:'',onSave,onDelete:vi.fn()})
 const select=host.querySelector('select');select.value='AU';select.dispatchEvent(new Event('change',{bubbles:true}));await tick()
 const input=host.querySelector('input');input.value='0412345678';input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('blur'));await tick()
 expect(onSave).not.toHaveBeenCalled()
 button('Save').click();await tick()
 expect(onSave).toHaveBeenCalledTimes(1)
 expect(onSave.mock.calls[0][0].value).toBe('+61412345678')
})
it('cancels editing an existing mobile without saving or rewriting it',async()=>{
 const onSave=vi.fn()
 await mount({value:'+919876543210',onSave,onDelete:vi.fn()})
 button('Edit').click();await tick()
 const input=host.querySelector('input');input.value='123';input.dispatchEvent(new Event('input',{bubbles:true}));await tick()
 button('Cancel').click();await tick()
 expect(onSave).not.toHaveBeenCalled()
 expect(host.textContent).toContain('+919876543210')
})
