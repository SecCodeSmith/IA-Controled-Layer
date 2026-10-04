import { Link } from 'react-router-dom'
import { StatusBadge } from '../common/StatusBadge'
import { formatDuration } from '../../lib/formatMs'
import { formatStep, stageRule } from '../../lib/scenarioText'
import type { Scenario } from '../../types/attack'

function StepList({ scenario, muted }: { scenario: Scenario; muted?: boolean }) {
  if (!scenario.steps?.length) return null
  return (
    <ul className={`m-0 list-none p-0 font-mono text-xs ${muted ? 'text-muted' : ''}`}>
      {scenario.steps.map((step, index) => (
        <li key={index} className="break-words">
          {formatStep(step)}
        </li>
      ))}
    </ul>
  )
}

function Label({ children }: { children: string }) {
  return <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">{children}</span>
}

function TraceTable({ scenario }: { scenario: Scenario }) {
  if (!scenario.trace?.length) return null
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] border-collapse text-xs">
        <thead>
          <tr className="text-left text-muted">
            <th className="py-1 pr-2 font-medium">Target</th>
            <th className="py-1 pr-2 font-medium">Status</th>
            <th className="py-1 pr-2 font-medium">Stage · rule</th>
            <th className="py-1 pr-2 font-medium">Reason</th>
            <th className="py-1 font-medium">Call</th>
          </tr>
        </thead>
        <tbody>
          {scenario.trace.map((entry, index) => (
            <tr key={index} className="border-t border-border-soft align-top">
              <td className="py-1 pr-2 font-mono">{entry.target}</td>
              <td className="py-1 pr-2">
                <StatusBadge status={entry.status} />
              </td>
              <td className="py-1 pr-2 text-muted">{stageRule(entry.stage, entry.rule_id)}</td>
              <td className="py-1 pr-2 text-muted">{entry.reason ?? '–'}</td>
              <td className="py-1 font-mono">
                {entry.call_id ? <Link to={`/admin/audit/${entry.call_id}`}>{entry.call_id}</Link> : '–'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ScenarioDetail({ scenario, id }: { scenario: Scenario; id: string }) {
  const status = scenario.status ?? 'PENDING'
  const hasResult = status !== 'PENDING' && status !== 'RUNNING'
  const observed = scenario.observed

  return (
    <div id={id} className="flex flex-col gap-3 rounded-lg bg-page px-3 py-3 text-[13px]">
      {scenario.description ? <p className="m-0 leading-snug">{scenario.description}</p> : null}

      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <span>
          <Label>Actor</Label> <span className="font-mono text-xs">{scenario.actor}</span>
        </span>
        <span>
          <Label>Expected</Label> {scenario.expected.status}{' '}
          <span className="text-muted">{stageRule(scenario.stage, scenario.expected.rule_id)}</span>
        </span>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>What it does</Label>
        {scenario.agent_driven && scenario.prompt ? (
          <>
            <blockquote className="m-0 border-l-2 border-border pl-3 italic">{scenario.prompt}</blockquote>
            {scenario.steps?.length ? <span className="text-xs text-muted">scripted fallback</span> : null}
            <StepList scenario={scenario} muted />
          </>
        ) : (
          <StepList scenario={scenario} />
        )}
      </div>

      {hasResult ? (
        <div className="flex flex-col gap-1.5">
          <Label>Result</Label>
          {scenario.explanation ? <p className="m-0 leading-snug">{scenario.explanation}</p> : null}
          {scenario.error ? (
            <p className="m-0 leading-snug" style={{ color: '#A3301A' }}>
              {scenario.error}
            </p>
          ) : null}
          {observed ? (
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={observed.status} />
              <span className="text-muted">{stageRule(observed.stage, observed.rule_id)}</span>
              {observed.reason ? <span className="text-muted">— {observed.reason}</span> : null}
            </div>
          ) : null}
          <span className="text-xs text-muted">
            {scenario.duration_ms !== null && scenario.duration_ms !== undefined
              ? `duration ${formatDuration(scenario.duration_ms)}`
              : ''}
            {scenario.via ? ` · via ${scenario.via}` : ''}
          </span>
          <TraceTable scenario={scenario} />
        </div>
      ) : null}
    </div>
  )
}
