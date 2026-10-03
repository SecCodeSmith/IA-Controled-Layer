export interface AuditFilterValue {
  user: string
  status: string
  kind: string
}

const STATUS_OPTIONS = ['', 'ALLOWED', 'MASKED', 'BLOCKED', 'ESCALATED', 'FLAGGED']
const KIND_OPTIONS = ['', 'tool_call', 'chat']

export function AuditFilters({
  value,
  onChange,
}: {
  value: AuditFilterValue
  onChange: (value: AuditFilterValue) => void
}) {
  return (
    <div className="flex flex-wrap gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="audit-user" className="text-xs text-muted">
          User
        </label>
        <input
          id="audit-user"
          type="text"
          value={value.user}
          placeholder="All users"
          onChange={(event) => onChange({ ...value, user: event.target.value })}
          className="min-h-10 w-40 rounded-md border border-border bg-white px-2.5 text-sm"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="audit-status" className="text-xs text-muted">
          Status
        </label>
        <select
          id="audit-status"
          value={value.status}
          onChange={(event) => onChange({ ...value, status: event.target.value })}
          className="min-h-10 rounded-md border border-border bg-white px-2.5 text-sm"
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option || 'All statuses'}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="audit-kind" className="text-xs text-muted">
          Kind
        </label>
        <select
          id="audit-kind"
          value={value.kind}
          onChange={(event) => onChange({ ...value, kind: event.target.value })}
          className="min-h-10 rounded-md border border-border bg-white px-2.5 text-sm"
        >
          {KIND_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option || 'All kinds'}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}
