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
