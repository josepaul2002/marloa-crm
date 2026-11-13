import { describe, expect, it } from 'vitest'
import { chartElements, mergePeople } from '../../src/utils/peopleMap'
const person = (id, manager_id = '', extra = {}) => ({ id, name: id, title: 'Director', department: 'Operations', manager_id, relationship: 'confirmed', ...extra })
describe('people map', () => {
  it('keeps reviewed people and maps newly selected manager IDs', () => {
    const saved = [person('boss', '', { notes: 'Manually verified' })]
    const result = mergePeople(saved, [person('p1', '', { name: 'boss' }), person('p2', 'p1')])
    expect(result).toHaveLength(2)
    expect(result[0].notes).toBe('Manually verified')
    expect(result[1].manager_id).toBe('boss')
  })
  it('does not assign a manager who was not selected', () => {
    expect(mergePeople([], [person('p2', 'p1')])[0].manager_id).toBe('')
  })
  it('collapses all descendants but keeps unrelated departments', () => {
    const graph = chartElements([person('a'), person('b', 'a'), person('c', 'b'), person('d')], new Set(['a']))
    expect(graph.nodes.filter(n => n.type === 'person').map(n => n.id)).toEqual(['a', 'd'])
    expect(graph.edges).toHaveLength(0)
  })
  it('renders inferred edges differently and highlights search matches', () => {
    const graph = chartElements([person('a'), person('b', 'a', { relationship: 'inferred' })], new Set(), 'b')
    expect(graph.edges[0].style.strokeDasharray).toBe('6 4')
    expect(graph.nodes.find(n => n.id === 'b').data.matched).toBe(true)
  })
})
