export function meetingErrorMessage(error, fallback = 'Unable to complete this action. Please try again.') {
  const messages = Array.isArray(error?.messages) ? error.messages.filter(m => typeof m === 'string' && m.trim()) : []
  if (messages.length) return messages.join(' ')
  return error?.message && !error.message.startsWith('/api/') ? error.message : fallback
}
