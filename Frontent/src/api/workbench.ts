import { useMutation, useQuery } from '@tanstack/react-query'
import { adminApi } from './client'
import type { ResourceMatrixResponse, TraceRequest, TraceResponse } from '../types/workbench'

export const WORKBENCH_TRACE_PATH = '/api/workbench/trace'
export const WORKBENCH_RESOURCES_PATH = '/api/workbench/resources'

export function useTrace() {
  return useMutation({
    mutationFn: (request: TraceRequest) => adminApi.post<TraceResponse>(WORKBENCH_TRACE_PATH, request),
  })
}

export function useResourceMatrix() {
  return useQuery({
    queryKey: ['workbench', 'resources'],
    queryFn: () => adminApi.get<ResourceMatrixResponse>(WORKBENCH_RESOURCES_PATH),
  })
}
