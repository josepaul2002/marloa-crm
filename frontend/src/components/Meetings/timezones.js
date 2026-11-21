const familiarZones = {'Asia/Kolkata':'India — Kolkata (IST)', 'Australia/Sydney':'Australia — Sydney', 'UTC':'Coordinated Universal Time (UTC)'}
export const timezoneOptions = [...new Set(['Asia/Kolkata','Australia/Sydney',...(Intl.supportedValuesOf?.('timeZone') || [])])].map(value => ({value,label:familiarZones[value] || value.replaceAll('_',' ').split('/').reverse().join(' — ')}))
export function wallTime(instant, zone) {
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(instant)).map(p=>[p.type,p.value]))
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
}
export function instantFromWall(value, zone) {
  if (!value) return null
  const target=Date.parse(value.replace(' ','T').slice(0,19)+'Z')
  let guess=target
  for(let i=0;i<4;i++) {const shown=Date.parse(wallTime(guess,zone).replace(' ','T')+'Z');const delta=target-shown;if(!delta)return guess;guess+=delta}
  return null
}
