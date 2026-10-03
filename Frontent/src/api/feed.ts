import { useQuery } from '@tanstack/react-query'
import { adminApi } from './client'
import type { FeedListResponse } from '../types/feed'

export function useFeed() {
  return useQuery({
    queryKey: ['feed'],
    queryFn: () => adminApi.get<FeedListResponse>('/api/feed?limit=100'),
  })
}
