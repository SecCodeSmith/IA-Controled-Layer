import { formatMs } from './formatMs'
import type { LatencyStats } from '../types/feed'

export interface LatencyFields {
  overhead_ms?: number | null
  proxy_latency_ms?: number | null
  upstream_latency_ms?: number | null
}

function isNumber(value: number | null | undefined): value is number {
  return typeof value === 'number'
}

export function addedDelay(proxyMs: number, upstreamMs: number): number {
  return Math.max(0, proxyMs - upstreamMs)
}

export function overheadMs(row: LatencyFields): number | null {
  if (isNumber(row.overhead_ms)) return row.overhead_ms
  if (isNumber(row.proxy_latency_ms) && isNumber(row.upstream_latency_ms)) {
    return addedDelay(row.proxy_latency_ms, row.upstream_latency_ms)
  }
  return null
}

export function overheadCell(row: LatencyFields): { text: string; title: string | undefined } {
  const overhead = overheadMs(row)
  if (overhead === null) return { text: '–', title: undefined }
  const parts: string[] = []
  if (isNumber(row.proxy_latency_ms)) parts.push(`total ${formatMs(row.proxy_latency_ms)}`)
  if (isNumber(row.upstream_latency_ms)) parts.push(`upstream ${formatMs(row.upstream_latency_ms)}`)
  return { text: `+${formatMs(overhead)}`, title: parts.length > 0 ? parts.join(' · ') : undefined }
}

export function overheadPercentiles(latency: LatencyStats): { p50: number; p95: number } {
  return {
    p50: latency.overhead_p50_ms ?? addedDelay(latency.proxy_p50_ms, latency.upstream_p50_ms),
    p95: latency.overhead_p95_ms ?? addedDelay(latency.proxy_p95_ms, latency.upstream_p95_ms),
  }
}
