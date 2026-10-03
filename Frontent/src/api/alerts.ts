import { useQuery } from '@tanstack/react-query'
import { adminApi, adminExportUrl } from './client'
import type { AlertListResponse } from '../types/feed'

export function useAlerts() {
  return useQuery({
    queryKey: ['alerts'],
    queryFn: () => adminApi.get<AlertListResponse>('/api/alerts'),
  })
}

export function alertsExportUrl(): string {
  return adminExportUrl('/api/alerts/export')
}
