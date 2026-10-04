import { adminStreamUrl } from '../api/client'
import { useEventSource } from './useEventSource'
import type { AttackRunCompleteEvent, AttackScenarioStreamEvent } from '../types/attack'

const TERMINAL_EVENTS = ['run_complete']

export function useAttackRunStream(
  runId: string | null,
  onScenario: (event: AttackScenarioStreamEvent) => void,
  onComplete: (event: AttackRunCompleteEvent) => void,
) {
  const url = runId ? adminStreamUrl(`/api/attack-suite/runs/${runId}/stream`) : null

  return useEventSource(
    url,
    {
      scenario: (event) => {
        onScenario(JSON.parse(event.data) as AttackScenarioStreamEvent)
      },
      run_complete: (event) => {
        onComplete(JSON.parse(event.data) as AttackRunCompleteEvent)
      },
    },
    { terminalEvents: TERMINAL_EVENTS },
  )
}
