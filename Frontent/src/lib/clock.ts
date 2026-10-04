export function formatClock(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })
}

export function changedText(changedAt?: string | null, changedBy?: string | null): string | null {
  if (!changedAt) return null
  return `changed ${formatClock(changedAt)}${changedBy ? ` by ${changedBy}` : ''}`
}
