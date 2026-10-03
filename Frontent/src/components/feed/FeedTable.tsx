import { StatusBadge } from '../common/StatusBadge'
import { formatReason } from '../../lib/formatReason'
import { roleLabel } from '../../lib/roleLabel'
import type { FeedRow } from '../../types/feed'

export function FeedTable({ rows }: { rows: FeedRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-muted">
            <th className="px-6 py-3 font-medium">Time</th>
            <th className="px-3 py-3 font-medium">User · role</th>
            <th className="px-3 py-3 font-medium">Tool call</th>
            <th className="px-3 py-3 font-medium">Status</th>
            <th className="px-3 py-3 pr-6 font-medium">Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.call_id}-${row.time}-${row.status}-${row.rule_id ?? ""}`} className="border-t border-border-soft">
              <td className="whitespace-nowrap px-6 py-3 font-mono text-[13px] text-muted">
                {formatTime(row.time)}
              </td>
              <td className="whitespace-nowrap px-3 py-3">
                {row.user.name} · {roleLabel(row.user.role)}
              </td>
              <td className="px-3 py-3 font-mono text-[13px]">{row.target}</td>
              <td className="px-3 py-3">
                <StatusBadge status={row.status} />
              </td>
              <td className="px-3 py-3 pr-6 text-muted">{formatReason(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 ? <p className="px-6 py-6 text-sm text-muted">No calls yet.</p> : null}
    </div>
  )
}

function formatTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleTimeString(undefined, { hour12: false })
}
