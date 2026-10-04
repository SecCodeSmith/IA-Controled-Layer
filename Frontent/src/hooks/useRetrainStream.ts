import { adminStreamUrl } from '../api/client'
import { useEventSource } from './useEventSource'
import type { RetrainFailedEvent, RetrainProgressEvent, RetrainResult } from '../types/classifier'

const TERMINAL_EVENTS = ['retrain_complete', 'retrain_failed']

export function useRetrainStream(
  jobId: string | null,
  onProgress: (event: RetrainProgressEvent) => void,
  onComplete: (event: RetrainResult) => void,
  onFailed: (event: RetrainFailedEvent) => void,
) {
  const url = jobId ? adminStreamUrl(`/api/classifier/retrain/${jobId}/stream`) : null

  return useEventSource(
    url,
    {
      retrain_progress: (event) => {
        onProgress(JSON.parse(event.data) as RetrainProgressEvent)
      },
      retrain_complete: (event) => {
        onComplete(JSON.parse(event.data) as RetrainResult)
      },
      retrain_failed: (event) => {
        onFailed(JSON.parse(event.data) as RetrainFailedEvent)
      },
    },
    { terminalEvents: TERMINAL_EVENTS },
  )
}
