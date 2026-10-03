import { useQuery } from '@tanstack/react-query'
import { adminApi, adminExportUrl } from './client'
import type { AuditDetail, AuditListResponse } from '../types/audit'

export interface AuditFiltersInput {
  user?: string
  status?: string
  kind?: string
  limit?: number
}

function buildQuery(filters: AuditFiltersInput): string {
  const params = new URLSearchParams()
  if (filters.user) params.set('user', filters.user)
  if (filters.status) params.set('status', filters.status)
  if (filters.kind) params.set('kind', filters.kind)
  params.set('limit', String(filters.limit ?? 100))
  return params.toString()
}

export function useAuditList(filters: AuditFiltersInput = {}) {
  return useQuery({
    queryKey: ['audit', filters],
    queryFn: () => adminApi.get<AuditListResponse>(`/api/audit?${buildQuery(filters)}`),
  })
}

export function useAuditDetail(callId: string | undefined) {
  return useQuery({
    queryKey: ['audit', 'detail', callId],
    queryFn: () => adminApi.get<AuditDetail>(`/api/audit/${callId}`),
    enabled: Boolean(callId),
  })
}

export function auditExportUrl(format: 'jsonl' | 'csv' | 'xlsx'): string {
  return adminExportUrl(`/api/audit/export?format=${format}`)
}
