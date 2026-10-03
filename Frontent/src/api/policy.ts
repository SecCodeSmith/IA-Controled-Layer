import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminApi } from './client'
import type { PolicyResponse } from '../types/policy'

const POLICY_POLL_INTERVAL_MS = 2000

export function usePolicy() {
  return useQuery({
    queryKey: ['policy'],
    queryFn: () => adminApi.get<PolicyResponse>('/api/policy'),
    refetchInterval: POLICY_POLL_INTERVAL_MS,
  })
}

export function usePolicyReload() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => adminApi.post<PolicyResponse>('/api/policy/reload'),
    onSuccess: (data) => {
      queryClient.setQueryData(['policy'], data)
    },
  })
}
