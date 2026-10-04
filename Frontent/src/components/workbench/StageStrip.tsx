import { PIPELINE_STAGE_ORDER, type PipelineStage } from '../../types/common'
import type { TracePoint, TraceStage } from '../../types/workbench'
import { StageChip } from '../common/StageChip'
import { formatMs } from '../../lib/formatMs'

const DEFAULT_LABEL = 'Pipeline stages'
const IDLE_ROW = 'idle'

interface StageRowData {
  key: string
  label: string
  visibleLabel: string | null
  stages: Map<PipelineStage, TraceStage> | null
}

function passLabel(point: TracePoint): string | null {
  return point === 'prompt' ? null : `${point} pass`
}

function buildRows(stages: TraceStage[] | null): StageRowData[] {
  if (!stages) return [{ key: IDLE_ROW, label: DEFAULT_LABEL, visibleLabel: null, stages: null }]
  const points = [...new Set(stages.map((stage) => stage.point))]
  if (points.length === 0) return [{ key: 'prompt', label: DEFAULT_LABEL, visibleLabel: null, stages: new Map() }]
  return points.map((point) => {
    const visibleLabel = passLabel(point)
    return {
      key: point,
      label: visibleLabel ?? DEFAULT_LABEL,
      visibleLabel,
      stages: new Map(stages.filter((stage) => stage.point === point).map((stage) => [stage.stage, stage])),
    }
  })
}

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

function StageRow({ row }: { row: StageRowData }) {
  return (
    <div className="flex flex-col gap-1.5">
      {row.visibleLabel ? <span className="text-xs font-medium text-muted">{row.visibleLabel}</span> : null}
      <ol
        aria-label={row.label}
        className="m-0 grid list-none grid-cols-2 gap-3 p-0 md:grid-cols-4 xl:grid-cols-7"
      >
        {PIPELINE_STAGE_ORDER.map((name) => {
          const stage = row.stages?.get(name)
          return (
            <li
              key={name}
              data-stage={name}
              data-testid={`stage-${row.key}-${name}`}
              className="flex min-h-[88px] flex-col items-start gap-1.5 rounded-[10px] border border-border bg-white px-4 py-3"
            >
              <StageChip stage={name} />
              {stage ? (
                <StageDetails stage={stage} />
              ) : (
                <span className="text-sm text-muted">{row.stages ? 'skipped' : '—'}</span>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export function StageStrip({ stages }: { stages: TraceStage[] | null }) {
  return (
    <div className="flex flex-col gap-3">
      {buildRows(stages).map((row) => (
        <StageRow key={row.key} row={row} />
      ))}
    </div>
  )
}
