import { createApp, h, nextTick, ref } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'
import InternationalPhoneInput from '@/components/Controls/InternationalPhoneInput.vue'
let app, host, value, updates
async function mount(initial = '') {
  value = ref(initial)
  updates = []
  host = document.createElement('div')
  document.body.append(host)
  app = createApp({
    render: () =>
      h(InternationalPhoneInput, {
        modelValue: value.value,
        'onUpdate:modelValue': (v) => {
          value.value = v
          updates.push(v)
        },
      }),
  })
  app.mount(host)
  await nextTick()
}
async function type(text) {
  const input = host.querySelector('input')
  input.value = text
  input.dispatchEvent(new Event('input', { bubbles: true }))
  await nextTick()
}
afterEach(() => {
  app?.unmount()
  host?.remove()
})
describe('dialling-code selector', () => {
  it('renders code and number together without writing to an existing contact', async () => {
    await mount('+61412345678')
    expect(host.querySelector('select').value).toBe('AU')
    expect(host.querySelector('input').value).toBe('412345678')
    expect(updates).toEqual([])
    expect(host.querySelector('select').getAttribute('aria-label')).toContain(
      'dialling code',
    )
  })
  it('switches to +61, accepts a national number and emits one international number', async () => {
    await mount()
    const select = host.querySelector('select')
    select.value = 'AU'
    select.dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    expect(value.value).toBe('')
    await type('0412 345 678')
    expect(value.value).toBe('+61412345678')
    expect(host.querySelector('input').value).toBe('0412 345 678')
  })
  it('recognises a pasted international number and keeps the prefix out of the local box', async () => {
    await mount()
    await type('+971 50 123 4567')
    expect(host.querySelector('select').value).toBe('AE')
    expect(host.querySelector('input').value).toBe('501234567')
    expect(value.value).toBe('+971501234567')
  })
  it('reports incomplete input on blur and clearing removes the entire saved number', async () => {
    await mount()
    await type('123')
    host.querySelector('input').dispatchEvent(new Event('blur'))
    await nextTick()
    expect(host.querySelector('[role="alert"]').textContent).toContain(
      'complete',
    )
    await type('')
    expect(value.value).toBe('')
    expect(host.querySelector('[role="alert"]')).toBeNull()
  })
})
