export function formatToolCall(tool: string, args: Record<string, unknown>): string {
  const parts = Object.entries(args).map(([key, value]) => `${key}=${formatArgValue(value)}`)
  return `${tool}(${parts.join(', ')})`
}

function formatArgValue(value: unknown): string {
  if (typeof value === 'string') return `"${value}"`
  if (value === null || value === undefined) return 'null'
  return JSON.stringify(value)
}
