import { useQuery } from '@tanstack/react-query'
import { adminApi } from './client'
import type { StatsResponse } from '../types/feed'

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: () => adminApi.get<StatsResponse>('/api/stats'),
  })
}
