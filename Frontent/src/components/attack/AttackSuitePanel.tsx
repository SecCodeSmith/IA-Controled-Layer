import { useState } from 'react'
import { useRunAttackSuite } from '../../api/attack'
import { useAttackRunStream } from '../../hooks/useAttackRunStream'
import { StatusBadge } from '../common/StatusBadge'
import { ErrorBanner } from '../common/ErrorBanner'
import { errorMessage } from '../../lib/errorMessage'
import type { AttackAgentMode, AttackRun, Scenario } from '../../types/attack'

function withScenarioUpdate(run: AttackRun, id: string, patch: Partial<Scenario>): AttackRun {
  return {
    ...run,
    scenarios: run.scenarios.map((scenario) => (scenario.id === id ? { ...scenario, ...patch } : scenario)),
  }
}

export function AttackSuitePanel() {
  const [agentMode, setAgentMode] = useState<AttackAgentMode>('scripted')
  const [run, setRun] = useState<AttackRun | null>(null)
  const runMutation = useRunAttackSuite()

  useAttackRunStream(
    run?.run_id ?? null,
    (event) => {
      setRun((prev) =>
        prev
          ? withScenarioUpdate(prev, event.id, {
              status: event.status,
              observed: event.observed,
              duration_ms: event.duration_ms,
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

  const total = run?.scenarios.length ?? 0
  const complete = run?.scenarios.filter((s) => s.status && s.status !== 'PENDING' && s.status !== 'RUNNING').length ?? 0
  const progressPercent = total > 0 ? Math.round((complete / total) * 100) : 0
  const summary = run?.summary

  return (
    <section className="flex flex-1 basis-[360px] flex-col gap-4 rounded-[10px] border border-border bg-white px-6 py-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">
          Attack suite{run ? ` · run #${run.number}` : ''}
        </h2>
        <span className="text-[13px] text-muted">
          {run ? `${complete} of ${total} scenarios complete` : 'No run yet'}
        </span>
      </div>

      <div className="h-2 rounded-full bg-border-soft">
        <div className="h-2 rounded-full bg-accent" style={{ width: `${progressPercent}%` }} />
      </div>

      <div className="flex flex-col">
        {run?.scenarios.map((scenario) => (
          <div
            key={scenario.id}
            className="flex items-center justify-between gap-3 border-t border-border-soft py-2.5 first:border-t-0"
          >
            <span className="text-sm leading-tight">{scenario.name}</span>
            <StatusBadge status={scenario.status ?? 'PENDING'} />
          </div>
        ))}
      </div>

      {summary ? (
        <div className="flex flex-col gap-1 rounded-lg bg-page px-4 py-3.5">
          <span className="text-[15px] font-semibold">
            {summary.stopped} attacks stopped · {summary.succeeded} succeeded
          </span>
          <span className="text-[13px] text-muted">
            {summary.running} running · {summary.pending} pending
          </span>
        </div>
      ) : null}

      <span className="font-mono text-xs text-muted">
        $ python attack_suite.py --target localhost:8080
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
