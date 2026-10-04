import type { ClassifierBand, ClassifierTrace, PathStep } from '../../types/workbench'
import { formatThreshold } from '../../lib/formatThreshold'

const BAND_STYLES: Record<ClassifierBand, { bg: string; fg: string }> = {
  block: { bg: '#FADFD7', fg: '#A3301A' },
  inconclusive: { bg: '#F8ECCF', fg: '#7A4E00' },
  allow: { bg: '#E2F0E8', fg: '#17613F' },
}

function Badge({ children, bg, fg }: { children: string; bg: string; fg: string }) {
  return (
    <span className="rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ background: bg, color: fg }}>
      {children}
    </span>
  )
}

function PathStepItem({ step }: { step: PathStep }) {
  const present = step.value > 0
  return (
    <li
      data-present={present}
      className="flex items-center gap-2 rounded px-2 py-1 font-mono text-[13px]"
      style={present ? { background: '#F8ECCF' } : undefined}
    >
      <span>{`${step.feature} ${step.direction} ${formatThreshold(step.threshold)}`}</span>
      {present ? <span className="text-[11px] text-muted">in text</span> : null}
    </li>
  )
}

export function DecisionTreeCard({ trace }: { trace: ClassifierTrace }) {
  const { explanation } = trace
  const percent = Math.round(trace.probability * 100)
  const band = BAND_STYLES[trace.band]

  return (
    <article className="flex flex-col gap-3 rounded-lg border border-border-soft px-4 py-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="m-0 text-[15px] font-semibold">Decision tree</h3>
        <div className="flex items-center gap-2">
          <Badge {...band}>{trace.band}</Badge>
          {trace.sampled ? <Badge bg="#E3E9F8" fg="#2348B8">sampled</Badge> : null}
          {trace.forced ? <Badge bg="#E3E9F8" fg="#2348B8">forced</Badge> : null}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div
          role="progressbar"
          aria-label="Injection probability"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          className="h-2 flex-1 rounded-full bg-border-soft"
        >
          <div className="h-2 rounded-full bg-accent" style={{ width: `${percent}%` }} />
        </div>
        <span className="font-mono text-[13px]">p = {trace.probability.toFixed(2)}</span>
      </div>

      <ul className="m-0 flex list-none flex-col gap-0.5 p-0" aria-label="Decision path">
        {explanation.path.map((step, index) => (
          <PathStepItem key={`${step.feature}-${index}`} step={step} />
        ))}
      </ul>

      {explanation.leaf ? (
        <span className="text-[13px] text-muted">
          Leaf #{explanation.leaf.node_id} · {explanation.leaf.samples} samples ·{' '}
          {Math.round(explanation.leaf.positive_fraction * 100)}% positive
        </span>
      ) : null}
      {explanation.top_features.length > 0 ? (
        <span className="text-xs text-muted">top features: {explanation.top_features.join(', ')}</span>
      ) : null}
    </article>
  )
}
