import type { CallStatus } from '../types/common'

const DECISION_LABELS: Record<CallStatus, string> = {
  ALLOWED: 'Allowed',
  MASKED: 'Allowed, response masked',
  BLOCKED: 'Blocked',
  ESCALATED: 'Escalated, pending approval',
  FLAGGED: 'Allowed, flagged for review',
}

export function formatDecision(status: CallStatus): string {
  return DECISION_LABELS[status]
}
