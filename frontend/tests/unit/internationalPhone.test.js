import { describe, expect, it } from 'vitest'
import {
  callingCode,
  diallingOptions,
  phoneError,
  phoneValue,
  splitPhone,
} from '@/utils/internationalPhone'

describe('international mobile input', () => {
  it('offers India, Australia, UAE and the complete metadata country list', () => {
    const options = diallingOptions()
    expect(options.length).toBeGreaterThan(200)
    expect(new Set(options.map((o) => o.country)).size).toBe(options.length)
    expect(options.find((o) => o.country === 'IN').code).toBe('+91')
    expect(options.find((o) => o.country === 'AU').code).toBe('+61')
    expect(options.find((o) => o.country === 'AE').code).toBe('+971')
    expect(callingCode('invalid')).toBe('')
  })
  it.each([
    ['+919876543210', 'IN', '9876543210'],
    ['+61412345678', 'AU', '412345678'],
    ['+971501234567', 'AE', '501234567'],
    ['+14165551234', 'CA', '4165551234'],
    ['0061412345678', 'AU', '412345678'],
  ])(
    'recognises %s without duplicating its dialling code',
    (value, country, national) => {
      expect(splitPhone(value)).toEqual({ country, national })
      expect(phoneValue(national, country)).toBe(
        value.startsWith('00') ? '+' + value.slice(2) : value,
      )
    },
  )
  it.each([
    ['09876543210', 'IN', '+919876543210'],
    ['0412 345 678', 'AU', '+61412345678'],
    ['050 123 4567', 'AE', '+971501234567'],
    ['٩٨٧٦٥٤٣٢١٠', 'IN', '+919876543210'],
  ])(
    'normalises national input %s with its selected numbering plan',
    (value, country, expected) => {
      expect(phoneValue(value, country)).toBe(expected)
      expect(phoneError(expected)).toBe('')
    },
  )
  it('does not rewrite legacy values during read or assume a country for global numbers', () => {
    expect(splitPhone('555-0100')).toEqual({
      country: 'IN',
      national: '555-0100',
    })
    expect(splitPhone('+80012345678')).toEqual({
      country: 'ZZ',
      national: '+80012345678',
    })
    expect(phoneValue('+80012345678', 'ZZ')).toBe('+80012345678')
  })
  it('rejects letters, unknown codes and incomplete numbers instead of extracting a number', () => {
    for (const value of [
      'Call +919876543210',
      '+9991234567',
      '+91',
      '+91123',
      '+919876543210123456',
    ]) {
      expect(phoneError(value)).not.toBe('')
    }
    expect(phoneValue('Call 9876543210', 'IN')).toBe('Call 9876543210')
    expect(phoneError('')).toBe('')
  })
  it('never saves a country code alone as a phone number', () => {
    expect(phoneValue('', 'AU')).toBe('')
    expect(phoneValue('   ', 'IN')).toBe('')
  })
  it('keeps a chosen country when an international prefix is shared', () => {
    expect(splitPhone('+1', 'CA').country).toBe('CA')
  })
})
