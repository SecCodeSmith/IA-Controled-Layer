import type { ResourceGrantView } from '../types/workbench'

function list(values: string[]): string {
  return values.join(', ')
}

function describeRow(attribute: string, expected: string | string[]): string {
  return Array.isArray(expected)
    ? `rows ${attribute} in ${list(expected)}`
    : `rows ${attribute} = ${expected}`
}

export function summarizeGrant(grant: ResourceGrantView): string[] {
  const lines: string[] = []
  if (grant.paths?.allow.length) lines.push(`paths allow ${list(grant.paths.allow)}`)
  if (grant.paths?.deny.length) lines.push(`paths deny ${list(grant.paths.deny)}`)
  if (grant.columns?.allow?.length) lines.push(`columns allow ${list(grant.columns.allow)}`)
  if (grant.columns?.deny.length) lines.push(`columns deny ${list(grant.columns.deny)}`)
  for (const [attribute, expected] of Object.entries(grant.rows)) {
    lines.push(describeRow(attribute, expected))
  }
  return lines
}
