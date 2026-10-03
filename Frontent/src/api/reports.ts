import { useQuery } from '@tanstack/react-query'
import { adminApi, adminExportUrl } from './client'
import type { SecurityReport } from '../types/reports'

export function useSecurityReport(period = '24h') {
  return useQuery({
    queryKey: ['reports', 'security', period],
    queryFn: () => adminApi.get<SecurityReport>(`/api/reports/security?period=${period}`),
  })
}

export { adminExportUrl }
