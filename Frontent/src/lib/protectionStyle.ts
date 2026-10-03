import type { ProtectionMode } from '../types/protection'

export const PROTECTION_LABELS: Record<ProtectionMode, string> = {
  enforce: 'Enforce',
  monitor: 'Monitor',
  off: 'Off',
}

export const PROTECTION_COLORS: Record<ProtectionMode, { bg: string; fg: string }> = {
  enforce: { bg: '#E2F0E8', fg: '#17613F' },
  monitor: { bg: '#F8ECCF', fg: '#7A4E00' },
  off: { bg: '#FADFD7', fg: '#A3301A' },
}
