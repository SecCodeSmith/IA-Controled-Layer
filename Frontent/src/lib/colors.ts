import type { CallStatus, ScenarioStatus } from '../types/common'

export interface ColorPair {
  bg: string
  fg: string
}

export const STATUS_COLORS: Record<CallStatus, ColorPair> = {
  ALLOWED: { bg: '#E2F0E8', fg: '#17613F' },
  MASKED: { bg: '#F8ECCF', fg: '#7A4E00' },
  BLOCKED: { bg: '#FADFD7', fg: '#A3301A' },
  ESCALATED: { bg: '#E3E9F8', fg: '#2348B8' },
  FLAGGED: { bg: '#ECEDEA', fg: '#5A5F66' },
}

export const SCENARIO_STATUS_COLORS: Record<ScenarioStatus, ColorPair> = {
  PENDING: { bg: '#ECEDEA', fg: '#5A5F66' },
  RUNNING: { bg: '#E3E9F8', fg: '#2348B8' },
  STOPPED: { bg: '#E2F0E8', fg: '#17613F' },
  PASSED: { bg: '#E2F0E8', fg: '#17613F' },
  SUCCEEDED: { bg: '#FADFD7', fg: '#A3301A' },
  NOT_ATTEMPTED: { bg: '#ECEDEA', fg: '#5A5F66' },
  ERROR: { bg: '#FADFD7', fg: '#A3301A' },
}

export const ALL_STATUS_COLORS: Record<string, ColorPair> = {
  ...STATUS_COLORS,
  ...SCENARIO_STATUS_COLORS,
}

export const AVATAR_PALETTE: ColorPair[] = [
  { bg: '#E3E9F8', fg: '#2348B8' },
  { bg: '#F8ECCF', fg: '#7A4E00' },
  { bg: '#E2F0E8', fg: '#17613F' },
  { bg: '#FADFD7', fg: '#A3301A' },
]

export function avatarColorFor(sub: string): ColorPair {
  let hash = 0
  for (let index = 0; index < sub.length; index += 1) {
    hash = (hash * 31 + sub.charCodeAt(index)) >>> 0
  }
  return AVATAR_PALETTE[hash % AVATAR_PALETTE.length]
}
