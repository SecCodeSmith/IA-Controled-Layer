import type { RetrainResult } from '../../types/classifier'

function Stat({ label, children }: { label: string; children: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="m-0 font-mono text-sm">{children}</dd>
    </div>
  )
}

function Outcome({ ok, children }: { ok: boolean; children: string }) {
  const colors = ok ? { bg: '#E2F0E8', fg: '#17613F' } : { bg: '#FADFD7', fg: '#A3301A' }
  return (
    <span className="rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ background: colors.bg, color: colors.fg }}>
      {children}
    </span>
  )
}

export function RetrainResultView({ result }: { result: RetrainResult }) {
  return (
    <div className="flex flex-wrap items-center gap-x-8 gap-y-3 rounded-lg bg-page px-4 py-3">
      <dl className="m-0 flex flex-wrap gap-x-8 gap-y-3">
        <Stat label="F1">{result.f1.toFixed(3)}</Stat>
        <Stat label="Version">{`v${result.version}`}</Stat>
        <Stat label="Training samples">{`${result.n_base} base + ${result.n_feedback} feedback`}</Stat>
      </dl>
      <div className="flex items-center gap-2">
        <Outcome ok={result.passed_gate}>{result.passed_gate ? 'gate passed' : 'gate failed'}</Outcome>
        <Outcome ok={result.swapped}>{result.swapped ? 'swapped' : 'not swapped'}</Outcome>
      </div>
    </div>
  )
}
