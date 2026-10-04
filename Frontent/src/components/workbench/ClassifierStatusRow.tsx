import type { ClassifierStatusResponse } from '../../types/classifier'

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="m-0 font-mono text-sm">{value}</dd>
    </div>
  )
}

function formatTrainedAt(value: string | null): string {
  if (!value) return '–'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export function ClassifierStatusRow({ status }: { status: ClassifierStatusResponse }) {
  const { tree, counts } = status
  return (
    <dl className="m-0 flex flex-wrap gap-x-8 gap-y-3 rounded-lg bg-page px-4 py-3">
      <Stat label="Model" value={tree.model_type ?? '–'} />
      <Stat label="F1" value={tree.f1 === null ? '–' : tree.f1.toFixed(3)} />
      <Stat label="Version" value={`v${tree.version}`} />
      <Stat label="Trained" value={formatTrainedAt(tree.trained_at)} />
      <Stat label="Pending" value={`${counts.pending} pending`} />
      <Stat label="Accepted" value={`${counts.accepted} accepted`} />
      <Stat label="Rejected" value={`${counts.rejected} rejected`} />
    </dl>
  )
}
