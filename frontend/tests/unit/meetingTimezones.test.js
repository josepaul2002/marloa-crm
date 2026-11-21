import { describe, it, expect } from 'vitest'
import { instantFromWall, wallTime } from '../../src/components/Meetings/timezones'
describe('meeting viewing time zones',()=>{
 it('preserves the same instant across employee zones',()=>{
  const instant=instantFromWall('2026-11-24 09:00:00','Asia/Kolkata')
  expect(wallTime(instant,'Australia/Sydney')).toBe('2026-11-24 14:30:00')
  expect(instantFromWall(wallTime(instant,'Australia/Sydney'),'Australia/Sydney')).toBe(instant)
 })
 it('rejects nonexistent daylight saving local time',()=>{
  expect(instantFromWall('2026-10-04 02:30:00','Australia/Sydney')).toBeNull()
 })
})
