import { PROTECTION_COLORS, PROTECTION_LABELS } from '../../lib/protectionStyle'
import type { ProtectionMode } from '../../types/protection'

export function ProtectionBadge({ mode }: { mode: ProtectionMode }) {
  const colors = PROTECTION_COLORS[mode]
  return (
    <span
      className="whitespace-nowrap rounded-full px-3 py-1 text-[13px] font-semibold"
      style={{ background: colors.bg, color: colors.fg }}
      data-testid="protection-badge"
    >
      Protection: {PROTECTION_LABELS[mode]}
    </span>
  )
}
