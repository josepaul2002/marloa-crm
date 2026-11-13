export function mergePeople(saved, selected) {
  const result = saved.map((p) => ({ ...p }))
  const ids = new Map()
  for (const person of selected) {
    const existing = result.find((p) =>
      person.linkedin_url && p.linkedin_url
        ? person.linkedin_url.replace(/\/$/, '') === p.linkedin_url.replace(/\/$/, '')
        : p.name.toLowerCase() === person.name.toLowerCase() && p.title.toLowerCase() === person.title.toLowerCase(),
    )
    const id = existing?.id || `research-${person.id}-${result.length}`
    ids.set(person.id, id)
    // Research never overwrites reviewed entries, even their manager or notes.
    if (!existing) result.push({ ...person, id, manager_id: '', contact: '' })
  }
  for (const person of selected) {
    const target = result.find((p) => p.id === ids.get(person.id))
    if (!saved.some((p) => p.id === target.id)) {
      target.manager_id = ids.get(person.manager_id) || ''
      if (!target.manager_id) target.relationship = 'unknown'
    }
  }
  return result
}

export function chartElements(people, collapsed = new Set(), query = '') {
  const byId = new Map(people.map((p) => [p.id, p]))
  const hidden = (p) => {
    const seen = new Set([p.id])
    while (p.manager_id && byId.has(p.manager_id)) {
      if (collapsed.has(p.manager_id)) return true
      if (seen.has(p.manager_id)) return false
      seen.add(p.manager_id)
      p = byId.get(p.manager_id)
    }
    return false
  }
  const visible = people.filter((p) => !hidden(p))
  const nodes = [], edges = []
  const roots = visible.filter((p) => !byId.has(p.manager_id))
  const groups = [...new Set(roots.map((p) => p.department || 'Unassigned'))].sort()
  let cursor = 0
  const placed = new Set()
  function place(person, depth) {
    if (placed.has(person.id)) return cursor
    placed.add(person.id)
    const children = visible.filter((p) => p.manager_id === person.id)
    const start = cursor
    const xs = children.map((p) => place(p, depth + 1))
    const x = xs.length ? (xs[0] + xs[xs.length - 1]) / 2 : cursor++ * 280
    nodes.push({ id: person.id, type: 'person', position: { x, y: depth * 190 + 80 },
      data: { ...person, collapsed: collapsed.has(person.id), reports: people.filter((p) => p.manager_id === person.id).length,
        matched: !!query && `${person.name} ${person.title} ${person.department}`.toLowerCase().includes(query.toLowerCase()) } })
    if (byId.has(person.manager_id)) edges.push({ id: `e-${person.id}`, source: person.manager_id, target: person.id,
      label: person.relationship === 'confirmed' ? 'Reviewed' : person.relationship === 'sourced' ? 'Source-backed · review' : 'Inferred',
      style: { stroke: person.relationship === 'confirmed' ? '#16a085' : '#9ca3af', strokeDasharray: person.relationship === 'confirmed' ? '0' : '6 4' } })
    if (cursor === start) cursor++
    return x
  }
  for (const group of groups) {
    const start = cursor * 280
    roots.filter((p) => (p.department || 'Unassigned') === group).forEach((p) => place(p, 0))
    nodes.push({ id: `department-${group}`, type: 'department', position: { x: start, y: 0 }, data: { label: group } })
    cursor++
  }
  return { nodes, edges }
}
