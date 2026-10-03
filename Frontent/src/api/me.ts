import { useQuery } from '@tanstack/react-query'
import { controlLayer } from './client'
import type { MeResponse } from '../types/identity'

export function useMe(enabled = true) {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => controlLayer.get<MeResponse>('/v1/me'),
    enabled,
  })
}
