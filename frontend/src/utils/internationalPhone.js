import {
  AsYouType,
  getCountries,
  getCountryCallingCode,
  parseDigits,
  parsePhoneNumberFromString,
} from 'libphonenumber-js/min'

const countries = getCountries()
const preferred = ['IN', 'AU', 'AE', 'US', 'GB', 'CA']
const names = new Intl.DisplayNames(['en'], { type: 'region' })
const supported = new Set(countries)
const allowed = /^[+\d\s().\-\u0660-\u0669\u06f0-\u06f9\uFF10-\uFF19]*$/

export function callingCode(country) {
  return supported.has(country) ? getCountryCallingCode(country) : ''
}

export function diallingOptions() {
  const rest = countries.filter((c) => !preferred.includes(c))
  rest.sort((a, b) => names.of(a).localeCompare(names.of(b)))
  return [...preferred, ...rest].map((country) => ({
    country,
    code: '+' + callingCode(country),
    label: '+' + callingCode(country) + ' · ' + names.of(country),
  }))
}

function internationalText(value) {
  const text = String(value || '').trim()
  return text.startsWith('00') ? '+' + text.slice(2) : text
}

// Read without writing: existing records must not change merely by opening a form.
export function splitPhone(value, currentCountry = 'IN') {
  const text = internationalText(value)
  const fallback = supported.has(currentCountry) ? currentCountry : 'IN'
  if (!text || !text.startsWith('+') || !allowed.test(text)) {
    return { country: fallback, national: String(value || '') }
  }
  const formatter = new AsYouType()
  formatter.input(text)
  const code = formatter.getCallingCode()
  if (!code) return { country: 'ZZ', national: text }
  const parsed = parsePhoneNumberFromString(text, { extract: false })
  const country =
    parsed?.country ||
    formatter.getCountry() ||
    (callingCode(fallback) === code ? fallback : undefined) ||
    preferred.find((c) => callingCode(c) === code) ||
    countries.find((c) => callingCode(c) === code)
  if (!country) return { country: 'ZZ', national: text }
  return {
    country,
    national: parsed?.nationalNumber || formatter.getNationalNumber(),
  }
}

export function phoneValue(national, country = 'IN') {
  const text = internationalText(national)
  if (!text) return ''
  // Keep invalid text visible and detectable; never silently extract a different number.
  if (!allowed.test(text)) return text
  const digits = parseDigits(text)
  if (!digits) return text.startsWith('+') ? text : ''
  const parsed = parsePhoneNumberFromString(text, {
    defaultCountry: supported.has(country) ? country : undefined,
    extract: false,
  })
  if (parsed) return parsed.number
  if (text.startsWith('+')) return '+' + digits
  const code = callingCode(country)
  return code ? '+' + code + digits : text
}

export function phoneError(value) {
  if (!value) return ''
  const text = internationalText(value)
  if (!text.startsWith('+') || !allowed.test(text)) {
    return 'Choose a dialling code and enter a phone number.'
  }
  const parsed = parsePhoneNumberFromString(text, { extract: false })
  return parsed?.isPossible() && !parsed.ext
    ? ''
    : 'Enter a complete phone number for the selected dialling code.'
}
