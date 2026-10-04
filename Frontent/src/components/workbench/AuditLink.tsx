import { Link } from 'react-router-dom'

export function AuditLink({ callId }: { callId: string }) {
  return (
    <Link to={`/admin/audit/${callId}`} className="text-[13px] text-accent underline">
      Audit record {callId}
    </Link>
  )
}
