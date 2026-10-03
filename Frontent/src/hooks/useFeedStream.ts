import { useQueryClient } from '@tanstack/react-query'
import { adminStreamUrl } from '../api/client'
import { useEventSource } from './useEventSource'
import type { FeedListResponse, FeedRow, StatsResponse } from '../types/feed'

const MAX_FEED_ROWS = 200

export function useFeedStream(enabled = true) {
  const queryClient = useQueryClient()
  const url = enabled ? adminStreamUrl('/api/feed/stream') : null

  return useEventSource(url, {
    feed: (event) => {
      const row = JSON.parse(event.data) as FeedRow
      queryClient.setQueryData<FeedListResponse>(['feed'], (prev) => {
        const items = prev?.items ?? []
        return { items: [row, ...items].slice(0, MAX_FEED_ROWS) }
      })
    },
    stats: (event) => {
      const stats = JSON.parse(event.data) as StatsResponse
      queryClient.setQueryData<StatsResponse>(['stats'], stats)
    },
    alert: () => {
      void queryClient.invalidateQueries({ queryKey: ['alerts'] })
    },
  })
}
