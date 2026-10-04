import { useMutation, useQuery } from '@tanstack/react-query'
import { adminApi } from './client'
import type { ResourceMatrixResponse, TraceRequest, TraceResponse } from '../types/workbench'

export function useTrace() {
  return useMutation({
    mutationFn: (request: TraceRequest) => adminApi.post<TraceResponse>('/api/workbench/trace', request),
  })
}

export function useResourceMatrix() {
  return useQuery({
    queryKey: ['workbench', 'resources'],
    queryFn: () => adminApi.get<ResourceMatrixResponse>('/api/workbench/resources'),
  })
}
