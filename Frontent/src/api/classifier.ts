import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminApi } from './client'
import type {
  ClassifierStatusResponse,
  CurateRequest,
  CurationSummary,
  RetrainJobResponse,
  RetrainRequest,
  SampleListResponse,
  SamplePatch,
  SampleStatus,
  TrainingSample,
} from '../types/classifier'

const CLASSIFIER_POLL_INTERVAL_MS = 3000
const SAMPLE_LIMIT = 100

export const CLASSIFIER_STATUS_PATH = '/api/classifier'
export const CLASSIFIER_SAMPLES_PATH = '/api/classifier/samples'

export function useClassifierStatus() {
  return useQuery({
    queryKey: ['classifier', 'status'],
    queryFn: () => adminApi.get<ClassifierStatusResponse>(CLASSIFIER_STATUS_PATH),
    refetchInterval: CLASSIFIER_POLL_INTERVAL_MS,
  })
}

export function useTrainingSamples(status: SampleStatus | null) {
  const query = status ? `status=${status}&limit=${SAMPLE_LIMIT}` : `limit=${SAMPLE_LIMIT}`
  return useQuery({
    queryKey: ['classifier', 'samples', status],
    queryFn: () => adminApi.get<SampleListResponse>(`${CLASSIFIER_SAMPLES_PATH}?${query}`),
    refetchInterval: CLASSIFIER_POLL_INTERVAL_MS,
  })
}

export function useInvalidateClassifier() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: ['classifier'] })
}

export function usePatchSample() {
  const invalidate = useInvalidateClassifier()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: SamplePatch }) =>
      adminApi.patch<TrainingSample>(`/api/classifier/samples/${id}`, patch),
    onSuccess: invalidate,
  })
}

export function useCurateSamples() {
  const invalidate = useInvalidateClassifier()
  return useMutation({
    mutationFn: (request: CurateRequest = {}) =>
      adminApi.post<CurationSummary>('/api/classifier/samples/curate', request),
    onSuccess: invalidate,
  })
}

export function useStartRetrain() {
  return useMutation({
    mutationFn: (request: RetrainRequest) =>
      adminApi.post<RetrainJobResponse>('/api/classifier/retrain', request),
  })
}
