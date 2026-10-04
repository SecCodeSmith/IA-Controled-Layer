import { useMemo, useState } from 'react'
import { useAttackScenarios, useRunAttackSuite } from '../../api/attack'
import { useModels } from '../../api/models'
import { useProtection } from '../../api/protection'
import { useAttackRunStream } from '../../hooks/useAttackRunStream'
import { ErrorBanner } from '../common/ErrorBanner'
import { ScenarioFilterBar } from './ScenarioFilterBar'
import { matchesFilter, type ScenarioFilter } from '../../lib/scenarioFilter'
import { ScenarioRow } from './ScenarioRow'
import { errorMessage } from '../../lib/errorMessage'
import { formatDuration } from '../../lib/formatMs'
import { buildReport } from '../../lib/scenarioText'
import { PIPELINE_STAGE_ORDER, type ScenarioStatus } from '../../types/common'
import type { AttackAgentMode, AttackRun, Scenario } from '../../types/attack'

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

function groupByStage(scenarios: Scenario[]): Array<{ stage: string; items: Scenario[] }> {
  return PIPELINE_STAGE_ORDER.map((stage) => ({
    stage: stage as string,
    items: scenarios
      .filter((scenario) => scenario.stage === stage)
      .sort((a, b) => Number(b.kind === 'positive') - Number(a.kind === 'positive')),
  })).filter((group) => group.items.length > 0)
}

export function AttackSuitePanel() {
  const [agentMode, setAgentMode] = useState<AttackAgentMode>('scripted')
  const [run, setRun] = useState<AttackRun | null>(null)
  const [filter, setFilter] = useState<ScenarioFilter>('all')
  const [query, setQuery] = useState('')
  const [copied, setCopied] = useState(false)
  const runMutation = useRunAttackSuite()
  const catalogue = useAttackScenarios()
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
              ...(event.trace !== undefined ? { trace: event.trace } : {}),
              ...(event.explanation !== undefined ? { explanation: event.explanation } : {}),
              ...(event.error !== undefined ? { error: event.error } : {}),
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

  const scenarios = useMemo<Scenario[]>(() => {
    const details = new Map((catalogue.data?.scenarios ?? []).map((scenario) => [scenario.id, scenario]))
    if (run) {
      return run.scenarios.map((scenario) => ({ ...details.get(scenario.id), ...scenario }))
    }
    return (catalogue.data?.scenarios ?? []).map((scenario) => ({ ...scenario, status: 'PENDING' as const }))
  }, [catalogue.data, run])

  const visible = useMemo(
    () =>
      scenarios.filter(
        (scenario) =>
          matchesFilter(scenario.status ?? 'PENDING', filter) &&
          scenario.name.toLowerCase().includes(query.trim().toLowerCase()),
      ),
    [scenarios, filter, query],
  )
  const groups = groupByStage(visible)

  const total = run ? scenarios.length : 0
  const running = count(scenarios, 'RUNNING')
  const pending = count(scenarios, 'PENDING')
  const complete = run ? total - running - pending : 0
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

  async function handleCopy() {
    if (!run) return
    try {
      await navigator.clipboard.writeText(buildReport(run, scenarios))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section className="flex flex-1 basis-[360px] flex-col gap-4 rounded-[10px] border border-border bg-white px-6 py-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-lg font-semibold">
          Attack suite{run ? ` · run #${run.number}` : ''}
        </h2>
        <span className="text-[13px] text-muted">
          {run
            ? `${complete} of ${total} scenarios complete`
            : `${scenarios.length} scenarios in the catalogue · no run yet`}
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

      <ScenarioFilterBar filter={filter} query={query} onFilter={setFilter} onQuery={setQuery} />

      <div className="flex flex-col gap-2">
        {groups.map((group) => (
          <div key={group.stage} className="flex flex-col">
            <div className="flex items-center justify-between pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
              <span>{group.stage}</span>
              <span>{group.items.length}</span>
            </div>
            {group.items.map((scenario) => (
              <ScenarioRow
                key={scenario.id}
                scenario={scenario}
                showScriptedChip={run?.agent === 'ollama'}
              />
            ))}
          </div>
        ))}
        {groups.length === 0 && scenarios.length > 0 ? (
          <span className="text-[13px] text-muted">No scenarios match this filter.</span>
        ) : null}
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
        {run ? (
          <button
            type="button"
            onClick={() => void handleCopy()}
            className="min-h-10 rounded-lg border border-border bg-white px-4 text-sm font-medium text-ink"
          >
            {copied ? 'Copied' : 'Copy report'}
          </button>
        ) : null}
      </div>
    </section>
  )
}
