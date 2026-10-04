import { useState } from 'react'
import { useClassifierStatus, useInvalidateClassifier, useStartRetrain } from '../../api/classifier'
import { useRetrainStream } from '../../hooks/useRetrainStream'
import { errorMessage } from '../../lib/errorMessage'
import type { RetrainResult } from '../../types/classifier'
import { ErrorBanner } from '../common/ErrorBanner'
import { RetrainResultView } from './RetrainResultView'

export function RetrainPanel() {
  const [includePending, setIncludePending] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [steps, setSteps] = useState<string[]>([])
  const [result, setResult] = useState<RetrainResult | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const start = useStartRetrain()
  const status = useClassifierStatus()
  const invalidateClassifier = useInvalidateClassifier()

  useRetrainStream(
    jobId,
    (event) => setSteps((previous) => [...previous, event.step]),
    (event) => {
      setResult(event)
      setJobId(null)
      void invalidateClassifier()
    },
    (event) => {
      setFailure(event.error)
      setJobId(null)
    },
  )

  const running = jobId !== null

  function handleRetrain() {
    setSteps([])
    setResult(null)
    setFailure(null)
    setJobId(null)
    start.mutate(
      { include_pending: includePending },
      {
        onSuccess: (job) => {
          if (job.result) setResult(job.result)
          else if (job.error) setFailure(job.error)
          else setJobId(job.job_id)
        },
      },
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={handleRetrain}
          disabled={start.isPending || running || status.isError}
          className="min-h-10 rounded-lg bg-ink px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          Retrain tree
        </button>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includePending}
            onChange={(event) => setIncludePending(event.target.checked)}
          />
          Include pending samples
        </label>
      </div>

      {start.isError ? <ErrorBanner message={errorMessage(start.error)} /> : null}
      {failure ? <ErrorBanner message={failure} /> : null}

      {steps.length > 0 ? (
        <ol aria-label="Retrain progress" className="m-0 flex list-none flex-col gap-1 p-0 font-mono text-[13px]">
          {steps.map((step, index) => (
            <li key={`${index}-${step}`}>{step}</li>
          ))}
        </ol>
      ) : null}

      {result ? <RetrainResultView result={result} /> : null}
    </div>
  )
}
