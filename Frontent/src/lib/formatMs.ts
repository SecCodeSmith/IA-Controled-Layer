export function formatMs(value: number): string {
  return `${Number(value.toFixed(2))} ms`
}

export function formatDuration(value: number): string {
  if (value < 1000) return `${Math.round(value)} ms`
  if (value < 60_000) return `${Number((value / 1000).toFixed(2))} s`
  const totalSeconds = Math.round(value / 1000)
  return `${Math.floor(totalSeconds / 60)} min ${totalSeconds % 60} s`
}
