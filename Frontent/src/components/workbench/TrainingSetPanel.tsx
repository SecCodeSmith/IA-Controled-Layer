import { useState } from 'react'
import {
  CLASSIFIER_SAMPLES_PATH,
  CLASSIFIER_STATUS_PATH,
  useClassifierStatus,
  useCurateSamples,
  usePatchSample,
  useTrainingSamples,
} from '../../api/classifier'
import { errorMessage } from '../../lib/errorMessage'
import type { CurationSummary, SampleStatus } from '../../types/classifier'
import { ErrorBanner } from '../common/ErrorBanner'
import { Spinner } from '../common/Spinner'
import { ClassifierStatusRow } from './ClassifierStatusRow'
import { EndpointErrorBanner } from './EndpointErrorBanner'
import { SamplesTable } from './SamplesTable'

const STATUS_FILTERS: SampleStatus[] = ['pending', 'accepted', 'rejected']

function describeSummary(summary: CurationSummary): string {
  return (
    `Judge reviewed ${summary.reviewed} · accepted ${summary.accepted} · ` +
    `rejected ${summary.rejected} · relabelled ${summary.relabelled} · refused ${summary.refused}`
  )
}

export function TrainingSetPanel() {
  const [statusFilter, setStatusFilter] = useState<SampleStatus | null>(null)
  const status = useClassifierStatus()
  const samples = useTrainingSamples(statusFilter)
  const patch = usePatchSample()
  const curate = useCurateSamples()

  return (
    <div className="flex flex-col gap-4">
      {status.isError ? <EndpointErrorBanner error={status.error} endpoint={CLASSIFIER_STATUS_PATH} /> : null}
      {status.data ? <ClassifierStatusRow status={status.data} /> : null}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="sample-status-filter" className="text-xs text-muted">
            Status filter
          </label>
          <select
            id="sample-status-filter"
            value={statusFilter ?? ''}
            onChange={(event) => setStatusFilter((event.target.value || null) as SampleStatus | null)}
            className="min-h-10 rounded-md border border-border bg-white px-2.5 text-sm"
          >
            <option value="">all</option>
            {STATUS_FILTERS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => curate.mutate({})}
          disabled={curate.isPending || status.isError}
          className="min-h-10 rounded-lg bg-ink px-4 text-sm font-semibold text-white disabled:opacity-50"
        >
          Curate with judge
        </button>
      </div>

      {curate.data ? <span className="text-[13px] text-muted">{describeSummary(curate.data)}</span> : null}
      {curate.data?.error ? <ErrorBanner message={curate.data.error} /> : null}
      {curate.isError ? <ErrorBanner message={errorMessage(curate.error)} /> : null}
      {patch.isError ? <ErrorBanner message={errorMessage(patch.error)} /> : null}

      {samples.isLoading ? <Spinner label="Loading samples…" /> : null}
      {samples.isError && !status.isError ? (
        <EndpointErrorBanner error={samples.error} endpoint={CLASSIFIER_SAMPLES_PATH} />
      ) : null}
      {samples.data ? (
        <SamplesTable samples={samples.data.items} onPatch={(id, change) => patch.mutate({ id, patch: change })} />
      ) : null}
    </div>
  )
}
