import { PIPELINE_STAGE_ORDER, type PipelineStage } from '../../types/common'
import type { TraceStage } from '../../types/workbench'
import { StageChip } from '../common/StageChip'
import { formatMs } from '../../lib/formatMs'

function StageDetails({ stage }: { stage: TraceStage }) {
  const firstRule = stage.violations[0]?.rule_id
  return (
    <>
      <span className="text-sm font-semibold">{stage.action}</span>
      {firstRule ? <span className="font-mono text-xs">{firstRule}</span> : null}
      <span className="font-mono text-xs text-muted">{formatMs(stage.timing_ms)}</span>
      {stage.cache_hit ? <span className="text-[11px] text-muted">cached</span> : null}
    </>
  )
}

function StageDetailsPlaceholder({ label }: { label: string }) {
  return <span className="text-sm text-muted">{label}</span>
}

interface StageStripProps {
  stages: TraceStage[] | null
}

export function StageStrip({ stages }: StageStripProps) {
  const byStage = new Map<PipelineStage, TraceStage>((stages ?? []).map((stage) => [stage.stage, stage]))

  return (
    <ol aria-label="Pipeline stages" className="m-0 grid list-none grid-cols-2 gap-3 p-0 md:grid-cols-4 xl:grid-cols-7">
      {PIPELINE_STAGE_ORDER.map((name) => {
        const stage = byStage.get(name)
        return (
          <li
            key={name}
            data-stage={name}
            data-testid={`stage-${name}`}
            className="flex min-h-[88px] flex-col items-start gap-1.5 rounded-[10px] border border-border bg-white px-4 py-3"
          >
            <StageChip stage={name} />
            {stage ? (
              <StageDetails stage={stage} />
            ) : (
              <StageDetailsPlaceholder label={stages ? 'skipped' : '—'} />
            )}
          </li>
        )
      })}
    </ol>
  )
}
