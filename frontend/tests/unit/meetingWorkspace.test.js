import { describe, it, expect } from 'vitest'
import { meetingIsPast, safeMeetingLink } from '../../src/utils/meetingWorkspace'
describe('meeting workspace', () => {
  it('uses site-time classification instead of the browser timezone', () => {
    expect(meetingIsPast({ status: 'Scheduled', is_past: false })).toBe(false)
    expect(meetingIsPast({ status: 'Scheduled', is_past: true })).toBe(true)
    expect(meetingIsPast({ status: 'Cancelled' })).toBe(true)
  })
  it('only opens https links', () => {
    expect(safeMeetingLink('javascript:alert(1)')).toBe(null)
    expect(safeMeetingLink('Office, Kochi')).toBe(null)
    expect(safeMeetingLink('https://meet.google.com/abc')).toBe('https://meet.google.com/abc')
  })
})
