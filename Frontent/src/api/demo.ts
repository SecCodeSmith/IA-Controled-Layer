import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ADMIN_TOKEN, adminApi } from './client'

export function useResetDemo() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => adminApi.post<{ ok: boolean }>('/api/demo/reset'),
    onSuccess: () => {
      void queryClient.invalidateQueries()
    },
  })
}

/** True when an admin token is configured (VITE_ADMIN_TOKEN), so the demo reset can be attempted. */
export function isAdminResetAvailable(): boolean {
  return Boolean(ADMIN_TOKEN)
}

/** Clears behavioural state (limits, budgets, sessions, approvals) but keeps logs. */
export function useResetBehavior() {
  return useMutation({
    mutationFn: () => adminApi.post<{ ok: boolean }>('/api/demo/reset?scope=behavior'),
  })
}
