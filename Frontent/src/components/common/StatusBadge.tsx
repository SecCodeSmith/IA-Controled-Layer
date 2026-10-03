import { ALL_STATUS_COLORS } from '../../lib/colors'

export function StatusBadge({ status }: { status: string }) {
  const colors = ALL_STATUS_COLORS[status] ?? { bg: '#ECEDEA', fg: '#5A5F66' }
  return (
    <span
      className="whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold"
      style={{ background: colors.bg, color: colors.fg }}
    >
      {status}
    </span>
  )
}
