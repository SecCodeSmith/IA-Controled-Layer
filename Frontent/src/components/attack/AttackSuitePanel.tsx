import { useState } from 'react'
import { useRunAttackSuite } from '../../api/attack'
import { useModels } from '../../api/models'
import { useProtection } from '../../api/protection'
import { useAttackRunStream } from '../../hooks/useAttackRunStream'
import { StatusBadge } from '../common/StatusBadge'
import { ErrorBanner } from '../common/ErrorBanner'
import { errorMessage } from '../../lib/errorMessage'
import { formatDuration } from '../../lib/formatMs'
import type { ScenarioStatus } from '../../types/common'
import type { AttackAgentMode, AttackRun, Scenario } from '../../types/attack'

const NOT_ATTEMPTED_HINT =
  'the model never attempted the risky action, so the control was not exercised'
const LEGEND =
  'STOPPED attack blocked · SUCCEEDED attack got through · PASSED compliant call allowed · NOT_ATTEMPTED model never tried it'

function withScenarioUpdate(run: AttackRun, id: string, patch: Partial<Scenario>): AttackRun {
  return {
    ...run,
    scenarios: run.scenarios.map((scenario) => (scenario.id === id ? { ...scenario, ...patch } : scenario)),
  }
}

function count(scenarios: Scenario[], status: ScenarioStatus): number {
  return scenarios.filter((scenario) => (scenario.status ?? 'PENDING') === status).length
}

interface RunContext {
  mode: string | undefined
  tier: AttackAgentMode
  provider: string | undefined
  model: string | undefined
}

function warningsFor(context: RunContext): string[] {
  const warnings: string[] = []
  if (context.mode && context.mode !== 'enforce') {
    warnings.push(
      `Protection is ${context.mode}: attacks are expected to get through. Switch to Enforce in the header for a meaningful run.`,
    )
  }
  if (context.tier === 'ollama' && context.provider && context.provider !== 'ollama') {
    warnings.push(
      `Active model is ${context.model} (${context.provider}); the ollama tier needs an Ollama model. Pick one in the model selector.`,
    )
  }
  return warnings
}

export function AttackSuitePanel() {
  const [agentMode, setAgentMode] = useState<AttackAgentMode>('scripted')
  const [run, setRun] = useState<AttackRun | null>(null)
  const runMutation = useRunAttackSuite()
  const protection = useProtection()
  const models = useModels()

  useAttackRunStream(
    run?.run_id ?? null,
    (event) => {
      setRun((prev) =>
        prev
          ? withScenarioUpdate(prev, event.id, {
              status: event.status,
              observed: event.observed,
              duration_ms: event.duration_ms,
              via: event.via ?? null,
            })
          : prev,
      )
    },
    (event) => {
      setRun((prev) => (prev ? { ...prev, summary: event.summary } : prev))
    },
  )

  async function handleRun() {
    const result = await runMutation.mutateAsync(agentMode)
    setRun(result)
  }

  const scenarios = run?.scenarios ?? []
  const total = scenarios.length
  const running = count(scenarios, 'RUNNING')
  const pending = count(scenarios, 'PENDING')
  const complete = total - running - pending
  const progressPercent = total > 0 ? Math.round((complete / total) * 100) : 0
  const incomplete = run !== null && complete < total
  const totalDuration = scenarios.reduce((sum, scenario) => sum + (scenario.duration_ms ?? 0), 0)

  const context: RunContext = run
    ? { mode: run.protection_mode, tier: run.agent, provider: run.provider, model: run.model }
    : {
        mode: protection.data?.mode,
        tier: agentMode,
        provider: models.data?.active.name,
        model: models.data?.active.model,
      }
  const warnings = warningsFor(context)

  return (
    <section className="flex flex-1 basis-[360px] flex-col gap-4 rounded-[10px] border border-border bg-white px-6 py-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">
          Attack suite{run ? ` · run #${run.number}` : ''}
        </h2>
        <span className="text-[13px] text-muted">
          {run ? `${complete} of ${total} scenarios complete` : 'No run yet'}
        </span>
        {run ? (
          <span className="text-xs text-muted">
            {run.model} via {run.provider} · protection {run.protection_mode} · agent tier {run.agent}
          </span>
        ) : null}
      </div>

      {warnings.map((warning) => (
        <div
          key={warning}
          role="alert"
          className="rounded-lg border px-3 py-2 text-[13px]"
          style={{ background: '#FBF3DC', borderColor: '#F0DDA6', color: '#7A4E00' }}
        >
          {warning}
        </div>
      ))}

      <div className="h-2 rounded-full bg-border-soft">
        <div className="h-2 rounded-full bg-accent" style={{ width: `${progressPercent}%` }} />
      </div>

      <div className="flex flex-col">
        {scenarios.map((scenario) => (
          <div
            key={scenario.id}
            className="flex items-center justify-between gap-3 border-t border-border-soft py-2.5 first:border-t-0"
          >
            <span className="min-w-0 text-sm leading-tight">{scenario.name}</span>
            <span className="flex shrink-0 items-center gap-1.5 whitespace-nowrap">
              {scenario.via === 'scripted' && run?.agent === 'ollama' ? (
                <span className="rounded bg-border-soft px-1.5 py-0.5 text-[11px] text-muted">scripted</span>
              ) : null}
              <span title={scenario.status === 'NOT_ATTEMPTED' ? NOT_ATTEMPTED_HINT : undefined}>
                <StatusBadge status={scenario.status ?? 'PENDING'} />
              </span>
              <span className="w-16 text-right font-mono text-xs text-muted" data-testid="scenario-duration" title="duration" aria-label="duration">
                {scenario.duration_ms === null ||
                scenario.duration_ms === undefined ||
                scenario.status === 'PENDING' ||
                scenario.status === 'RUNNING'
                  ? '–'
                  : formatDuration(scenario.duration_ms)}
              </span>
            </span>
          </div>
        ))}
      </div>

      {run ? (
        <>
          <span className="text-xs text-muted">{LEGEND}</span>
          <div className="flex flex-col gap-1 rounded-lg bg-page px-4 py-3.5">
            <span className="text-[15px] font-semibold">
              {count(scenarios, 'STOPPED')} attacks stopped · {count(scenarios, 'SUCCEEDED')} got through
            </span>
            <span className="text-[13px] text-muted">
              {count(scenarios, 'PASSED')} compliant passed · {count(scenarios, 'NOT_ATTEMPTED')} not
              attempted · {count(scenarios, 'ERROR')} errors
            </span>
            {!incomplete ? (
              <span className="text-[13px] text-muted">run time {formatDuration(totalDuration)}</span>
            ) : null}
            {incomplete ? (
              <span className="text-[13px] text-muted">
                {running} running · {pending} pending
              </span>
            ) : null}
          </div>
        </>
      ) : null}

      <span className="font-mono text-xs text-muted">
        $ python attack_suite.py --target localhost:8080{agentMode === 'ollama' ? ' --agent ollama' : ''}
      </span>

      {runMutation.isError ? <ErrorBanner message={errorMessage(runMutation.error)} /> : null}

      <div className="flex flex-wrap gap-2.5">
        <select
          value={agentMode}
          onChange={(event) => setAgentMode(event.target.value as AttackAgentMode)}
          className="min-h-10 rounded-md border border-border bg-white px-2.5 text-sm"
          aria-label="Attack suite agent"
        >
          <option value="scripted">scripted</option>
          <option value="ollama">ollama</option>
        </select>
        <button
          type="button"
          onClick={() => void handleRun()}
          disabled={runMutation.isPending}
          className="min-h-10 flex-1 rounded-lg bg-ink px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          Run attack suite
        </button>
      </div>
    </section>
  )
}
