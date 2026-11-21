export function meetingIsPast(meeting) {
  if (['Completed', 'Cancelled', 'No-show'].includes(meeting.status)) return true
  return Boolean(meeting.is_past)
}

export function safeMeetingLink(value) {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' ? url.href : null
  } catch {
    return null
  }
}
