import { useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from './client'

export function useResetDemo() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => adminApi.post<{ ok: boolean }>('/api/demo/reset'),
    onSuccess: () => {
      void queryClient.invalidateQueries()
    },
  })
}
