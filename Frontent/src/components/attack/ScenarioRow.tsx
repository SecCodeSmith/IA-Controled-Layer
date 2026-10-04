import { useState } from 'react'
import { StatusBadge } from '../common/StatusBadge'
import { ScenarioDetail } from './ScenarioDetail'
import { formatDuration } from '../../lib/formatMs'
import type { Scenario } from '../../types/attack'

const NOT_ATTEMPTED_HINT =
  'the model never attempted the risky action, so the control was not exercised'

interface ScenarioRowProps {
  scenario: Scenario
  showScriptedChip: boolean
}

export function ScenarioRow({ scenario, showScriptedChip }: ScenarioRowProps) {
  const [open, setOpen] = useState(false)
  const status = scenario.status ?? 'PENDING'
  const detailId = `scenario-detail-${scenario.id}`
  const waiting = status === 'PENDING' || status === 'RUNNING'

  return (
    <div className="border-t border-border-soft first:border-t-0">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={detailId}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 bg-transparent py-2 text-left"
      >
        <span className="min-w-0 text-sm leading-tight">{scenario.name}</span>
        <span className="flex shrink-0 items-center gap-1.5 whitespace-nowrap">
          {scenario.via === 'scripted' && showScriptedChip ? (
            <span className="rounded bg-border-soft px-1.5 py-0.5 text-[11px] text-muted">scripted</span>
          ) : null}
          <span title={status === 'NOT_ATTEMPTED' ? NOT_ATTEMPTED_HINT : undefined}>
            <StatusBadge status={status} />
          </span>
          <span
            className="w-16 text-right font-mono text-xs text-muted"
            data-testid="scenario-duration"
            title="duration"
            aria-label="duration"
          >
            {waiting || scenario.duration_ms === null || scenario.duration_ms === undefined
              ? '–'
              : formatDuration(scenario.duration_ms)}
          </span>
        </span>
      </button>
      {open ? (
        <div className="pb-2">
          <ScenarioDetail scenario={scenario} id={detailId} />
        </div>
      ) : null}
    </div>
  )
}
