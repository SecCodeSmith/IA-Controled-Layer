import type { DemoUser } from '../../types/identity'

interface ActorSelectProps {
  id: string
  label: string
  users: DemoUser[]
  value: string
  onChange: (actor: string) => void
}

export function ActorSelect({ id, label, users, value, onChange }: ActorSelectProps) {
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
        {users.map((user) => (
          <option key={user.sub} value={user.sub}>
            {user.name}
          </option>
        ))}
      </select>
    </div>
  )
}
