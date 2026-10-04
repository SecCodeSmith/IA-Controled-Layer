export type ScenarioFilter = 'all' | 'failed' | 'not_attempted' | 'ok'

export function matchesFilter(status: string, filter: ScenarioFilter): boolean {
  if (filter === 'failed') return status === 'SUCCEEDED' || status === 'ERROR'
  if (filter === 'not_attempted') return status === 'NOT_ATTEMPTED'
  if (filter === 'ok') return status === 'PASSED' || status === 'STOPPED'
  return true
}
