import { Link } from 'react-router-dom'
import { StatusBadge } from '../common/StatusBadge'
import { formatReason } from '../../lib/formatReason'
import { overheadCell } from '../../lib/overhead'
import { roleLabel } from '../../lib/roleLabel'
import type { AuditListItem } from '../../types/audit'

export function AuditTable({ items }: { items: AuditListItem[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-muted">
            <th className="px-6 py-3 font-medium">Time</th>
            <th className="px-3 py-3 font-medium">User · role</th>
            <th className="px-3 py-3 font-medium">Target</th>
            <th className="px-3 py-3 font-medium">Status</th>
            <th className="px-3 py-3 font-medium">Reason</th>
            <th className="px-3 py-3 pr-6 text-right font-medium">Added delay</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={`${item.call_id}-${item.time}-${item.status}-${item.rule_id ?? ""}`} className="border-t border-border-soft">
              <td className="whitespace-nowrap px-6 py-3 font-mono text-[13px] text-muted">
                {formatTime(item.time)}
              </td>
              <td className="whitespace-nowrap px-3 py-3">
                {item.user.name} · {roleLabel(item.user.role)}
              </td>
              <td className="px-3 py-3 font-mono text-[13px]">
                <Link to={`/admin/audit/${item.call_id}`} className="hover:underline">
                  {item.target}
                </Link>
              </td>
              <td className="px-3 py-3">
                <StatusBadge status={item.status} />
              </td>
              <td className="px-3 py-3 text-muted">{formatReason(item)}</td>
              <td
                className="whitespace-nowrap px-3 py-3 pr-6 text-right font-mono text-[13px] text-muted"
                title={overheadCell(item).title}
              >
                {overheadCell(item).text}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 ? <p className="px-6 py-6 text-sm text-muted">No calls match these filters.</p> : null}
    </div>
  )
}

function formatTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, { hour12: false })
}
