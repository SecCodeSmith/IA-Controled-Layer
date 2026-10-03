import { useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from './client'
import type { ClearLogsResponse } from '../types/protection'

export function useClearLogs() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => adminApi.post<ClearLogsResponse>('/api/logs/clear'),
    onSuccess: () => {
      void queryClient.invalidateQueries()
    },
  })
}
