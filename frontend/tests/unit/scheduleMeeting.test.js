import { createApp, h, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ScheduleMeeting from '../../src/components/Meetings/ScheduleMeeting.vue'

const { call } = vi.hoisted(() => ({ call: vi.fn() }))
vi.mock('frappe-ui', async (original) => ({ ...(await original()), call }))
let app, host
let googleState = 'connected'
beforeEach(() => {
  googleState = 'connected'
  call.mockImplementation(async method => {
    if (method.endsWith('connection_status')) return { status: googleState }
    if (method.endsWith('directory')) return { people: [], own_places: [], shared_places: [], me: 'me@example.com' }
    return { calendars: [{ name: 'Customer meetings' }] }
  })
})

afterEach(() => {
  app?.unmount()
  host?.remove()
  document.body.innerHTML = ''
  vi.clearAllMocks()
})

describe('meeting scheduling dialog', () => {
  it('renders its title and fields with the installed Frappe UI dialog', async () => {
    host = document.createElement('div')
    document.body.appendChild(host)
    app = createApp({ render: () => h(ScheduleMeeting, { modelValue: true, deal: 'DEAL-1' }) })
    app.config.globalProperties.__ = globalThis.__
    app.mount(host)
    await new Promise(resolve => setTimeout(resolve, 30))
    await nextTick()
    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog).not.toBeNull()
    expect(dialog.textContent).toContain('Schedule meeting')
    expect(dialog.textContent).toContain('Meeting title')
    expect(dialog.querySelector('form')).not.toBeNull()
    expect(dialog.textContent).toContain('Send invitation')
    expect(dialog.querySelector('input[type="datetime-local"]')).toBeNull()
    expect(dialog.querySelector('[aria-label="Google Contacts connected"]')).not.toBeNull()
    expect(dialog.textContent).not.toContain('Connect Google Contacts')
    expect(call).toHaveBeenCalledWith('crm.meetings.scheduling.scheduling_context', expect.objectContaining({ deal: 'DEAL-1' }))
  })
})

describe('editing personal hours while scheduling', () => {
  it('hides the meeting dialog for settings and resumes the unsent draft afterwards', async () => {
    const { showSettings } = await import('../../src/composables/settings')
    showSettings.value = false
    host = document.createElement('div'); document.body.appendChild(host)
    app = createApp({ render: () => h(ScheduleMeeting, { modelValue:true, deal:'DEAL-1' }) })
    app.config.globalProperties.__ = globalThis.__; app.mount(host)
    await new Promise(r => setTimeout(r,30)); await nextTick()
    const title = document.querySelector('form input')
    title.value = 'Unsent demo'; title.dispatchEvent(new Event('input',{bubbles:true})); await nextTick()
    const button = [...document.querySelectorAll('button')].find(b => b.textContent.includes('My availability'))
    button.click(); await nextTick(); await nextTick()
    expect(showSettings.value).toBe(true)
    showSettings.value = false; await nextTick(); await new Promise(r => setTimeout(r,30))
    expect(document.querySelector('form input').value).toBe('Unsent demo')
  })
})
