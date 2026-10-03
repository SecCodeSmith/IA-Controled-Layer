import { useMutation, useQuery } from '@tanstack/react-query'
import { adminApi } from './client'
import type { AttackAgentMode, AttackRun, ScenariosResponse } from '../types/attack'

export function useAttackScenarios() {
  return useQuery({
    queryKey: ['attack-suite', 'scenarios'],
    queryFn: () => adminApi.get<ScenariosResponse>('/api/attack-suite/scenarios'),
  })
}

export function useRunAttackSuite() {
  return useMutation({
    mutationFn: (agent: AttackAgentMode) =>
      adminApi.post<AttackRun>(`/api/attack-suite/run?agent=${agent}`),
  })
}

export function useAttackRun(runId: string | null) {
  return useQuery({
    queryKey: ['attack-suite', 'run', runId],
    queryFn: () => adminApi.get<AttackRun>(`/api/attack-suite/runs/${runId}`),
    enabled: Boolean(runId),
  })
}
