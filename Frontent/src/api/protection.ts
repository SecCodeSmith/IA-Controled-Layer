import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminApi } from './client'
import type { ProtectionMode, ProtectionState, RuleToggleResponse } from '../types/protection'

export function useProtection() {
  return useQuery({
    queryKey: ['protection'],
    queryFn: () => adminApi.get<ProtectionState>('/api/protection'),
  })
}

export function useSetProtection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (mode: ProtectionMode) => adminApi.put<ProtectionState>('/api/protection', { mode }),
    onSuccess: (data) => {
      queryClient.setQueryData(['protection'], data)
      void queryClient.invalidateQueries({ queryKey: ['policy'] })
      void queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })
}

export function useToggleRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ ruleId, enabled }: { ruleId: string; enabled: boolean }) =>
      adminApi.patch<RuleToggleResponse>(`/api/policy/rules/${ruleId}`, { enabled }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['policy'] })
      void queryClient.invalidateQueries({ queryKey: ['protection'] })
    },
  })
}

export function useClearOverrides() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => adminApi.delete<ProtectionState>('/api/protection/overrides'),
    onSuccess: (data) => {
      queryClient.setQueryData(['protection'], data)
      void queryClient.invalidateQueries({ queryKey: ['policy'] })
    },
  })
}
