export function formatResult(value: unknown): string {
  if (value === null || value === undefined) return '(none)'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}
