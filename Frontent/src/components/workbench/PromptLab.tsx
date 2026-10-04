import { useState } from 'react'
import { useTrace } from '../../api/workbench'
import { useActorChoice } from '../../hooks/useActorChoice'
import { errorMessage } from '../../lib/errorMessage'
import type { TraceResponse } from '../../types/workbench'
import { ErrorBanner } from '../common/ErrorBanner'
import { ActorSelect } from './ActorSelect'
import { DecisionTreeCard } from './DecisionTreeCard'
import { JudgeCard } from './JudgeCard'
import { TraceVerdict } from './TraceVerdict'

interface PromptLabProps {
  onTrace: (trace: TraceResponse) => void
}

export function PromptLab({ onTrace }: PromptLabProps) {
  const { users, actor, setActor } = useActorChoice()
  const [text, setText] = useState('')
  const [forceVerify, setForceVerify] = useState(false)
  const trace = useTrace()
  const result = trace.data

  function handleTrace() {
    trace.mutate({ actor, kind: 'prompt', text, force_verify: forceVerify }, { onSuccess: onTrace })
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-4">
        <ActorSelect id="prompt-lab-actor" label="Actor" users={users} value={actor} onChange={setActor} />
        <label className="flex min-h-10 items-center gap-2 text-sm">
          <input type="checkbox" checked={forceVerify} onChange={(event) => setForceVerify(event.target.checked)} />
          Force judge
        </label>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="prompt-lab-text" className="text-xs text-muted">
          Prompt
        </label>
        <textarea
          id="prompt-lab-text"
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={4}
          className="rounded-md border border-border bg-white px-3 py-2 font-mono text-[13px]"
        />
      </div>

      <div>
        <button
          type="button"
          onClick={handleTrace}
          disabled={trace.isPending || !actor || !text.trim()}
          className="min-h-10 rounded-lg bg-ink px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          Trace
        </button>
      </div>

      {trace.isError ? <ErrorBanner message={errorMessage(trace.error)} /> : null}

      {result ? (
        <div className="flex flex-col gap-3">
          <TraceVerdict trace={result} />
          {result.classifier_trace ? <DecisionTreeCard trace={result.classifier_trace} /> : null}
          {result.judge ? (
            <JudgeCard judge={result.judge} sampleId={result.training_sample_id} callId={result.call_id} />
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
