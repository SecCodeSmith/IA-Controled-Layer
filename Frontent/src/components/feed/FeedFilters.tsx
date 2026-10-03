export interface FeedFilterValue {
  user: string
  role: string
  status: string
}

interface FeedFiltersProps {
  userOptions: string[]
  roleOptions: string[]
  value: FeedFilterValue
  onChange: (value: FeedFilterValue) => void
}

const ALL_USERS = 'All users'
const ALL_ROLES = 'All roles'
const ALL_STATUSES = 'All statuses'
const STATUS_OPTIONS = [ALL_STATUSES, 'Allowed', 'Masked', 'Blocked', 'Escalated', 'Flagged']

export function FeedFilters({ userOptions, roleOptions, value, onChange }: FeedFiltersProps) {
  return (
    <div className="flex flex-wrap gap-3">
      <FilterSelect
        label="User"
        id="f-user"
        value={value.user}
        options={[ALL_USERS, ...userOptions]}
        onChange={(user) => onChange({ ...value, user })}
      />
      <FilterSelect
        label="Role"
        id="f-role"
        value={value.role}
        options={[ALL_ROLES, ...roleOptions]}
        onChange={(role) => onChange({ ...value, role })}
      />
      <FilterSelect
        label="Status"
        id="f-status"
        value={value.status}
        options={STATUS_OPTIONS}
        onChange={(status) => onChange({ ...value, status })}
      />
    </div>
  )
}

interface FilterSelectProps {
  label: string
  id: string
  value: string
  options: string[]
  onChange: (value: string) => void
}

function FilterSelect({ label, id, value, options, onChange }: FilterSelectProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs text-muted">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-10 rounded-md border border-border bg-white px-2.5 text-sm"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  )
}

export { ALL_USERS, ALL_ROLES, ALL_STATUSES }
