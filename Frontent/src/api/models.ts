import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminApi } from './client'
import type { ModelsResponse } from '../types/protection'

export function useModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: () => adminApi.get<ModelsResponse>('/api/models'),
  })
}

export function useSelectModel() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ provider, model }: { provider: string; model: string }) =>
      adminApi.put<ModelsResponse['active']>('/api/models', { provider, model }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['models'] })
      void queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })
}
