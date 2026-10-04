import { useState } from 'react'
import { useTrace } from '../../api/workbench'
import { useActorChoice } from '../../hooks/useActorChoice'
import { errorMessage } from '../../lib/errorMessage'
import { parseProjection } from '../../lib/parseProjection'
import { formatResult } from '../../lib/formatResult'
import type { TraceResponse } from '../../types/workbench'
import { ErrorBanner } from '../common/ErrorBanner'
import { PreBlock } from '../common/PreBlock'
import { ActorSelect } from './ActorSelect'
import { AuditLink } from './AuditLink'
import { TraceVerdict } from './TraceVerdict'

const INVALID_ARGUMENTS = 'Arguments must be a valid JSON object'
const INPUT_CLASS = 'min-h-10 rounded-md border border-border bg-white px-2.5 text-sm'

function parseArguments(text: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(text)
    return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null
  } catch {
    return null
  }
}

function ResultBlock({ testId, title, text, tone }: { testId: string; title: string; text: unknown; tone?: 'danger' | 'success' }) {
  return (
    <div data-testid={testId} className="flex min-w-0 flex-1 basis-[280px] flex-col gap-1.5">
      <span className="text-xs text-muted">{title}</span>
      <PreBlock tone={tone}>{formatResult(text)}</PreBlock>
    </div>
  )
}

function Redactions({ trace }: { trace: TraceResponse }) {
  const projection = parseProjection(trace.stages)
  if (!projection) return null
  return (
    <div className="flex flex-col gap-0.5 text-[13px]">
      {projection.columnsRedacted.length > 0 ? (
        <span>Redacted columns: {projection.columnsRedacted.join(', ')}</span>
      ) : null}
      {projection.rowsFiltered > 0 ? <span>Rows filtered: {projection.rowsFiltered}</span> : null}
    </div>
  )
}

interface ResourceSimulatorProps {
  onTrace?: (trace: TraceResponse) => void
}

export function ResourceSimulator({ onTrace }: ResourceSimulatorProps) {
  const { users, actor, setActor } = useActorChoice()
  const [server, setServer] = useState('')
  const [tool, setTool] = useState('')
  const [argumentsText, setArgumentsText] = useState('{}')
  const [formError, setFormError] = useState<string | null>(null)
  const trace = useTrace()
  const result = trace.data

  function handleSimulate() {
    const parsed = parseArguments(argumentsText)
    if (!parsed) {
      setFormError(INVALID_ARGUMENTS)
      return
    }
    setFormError(null)
    trace.mutate(
      { actor, kind: 'tool_call', tool_call: { server: server.trim(), tool: tool.trim(), arguments: parsed } },
      { onSuccess: onTrace },
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-4">
        <ActorSelect id="simulator-actor" label="Simulator actor" users={users} value={actor} onChange={setActor} />
        <div className="flex flex-col gap-1">
          <label htmlFor="simulator-server" className="text-xs text-muted">
            Server
          </label>
          <input id="simulator-server" value={server} onChange={(event) => setServer(event.target.value)} className={INPUT_CLASS} />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="simulator-tool" className="text-xs text-muted">
            Tool
          </label>
          <input id="simulator-tool" value={tool} onChange={(event) => setTool(event.target.value)} className={INPUT_CLASS} />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="simulator-arguments" className="text-xs text-muted">
          Arguments (JSON)
        </label>
        <textarea
          id="simulator-arguments"
          value={argumentsText}
          onChange={(event) => setArgumentsText(event.target.value)}
          rows={3}
          className="rounded-md border border-border bg-white px-3 py-2 font-mono text-[13px]"
        />
      </div>

      <div>
        <button
          type="button"
          onClick={handleSimulate}
          disabled={trace.isPending || !actor || !server.trim() || !tool.trim()}
          className="min-h-10 rounded-lg bg-ink px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          Simulate
        </button>
      </div>

      {formError ? <ErrorBanner message={formError} /> : null}
      {trace.isError ? <ErrorBanner message={errorMessage(trace.error)} /> : null}

      {result ? (
        <div className="flex flex-col gap-3">
          <TraceVerdict trace={result} />
          <div className="flex flex-wrap gap-4">
            <ResultBlock testId="raw-result" title="Raw result" text={result.raw_result} />
            <ResultBlock testId="delivered-result" title="Delivered result" text={result.delivered_result} tone="success" />
          </div>
          <Redactions trace={result} />
          <AuditLink callId={result.call_id} />
        </div>
      ) : null}
    </div>
  )
}
