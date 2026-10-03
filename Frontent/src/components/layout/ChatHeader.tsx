import { ShieldLogo } from '../common/ShieldLogo'
import { Avatar } from '../common/Avatar'
import { roleLabel } from '../../lib/roleLabel'
import type { Identity } from '../../types/identity'

interface ChatHeaderProps {
  identity: Identity
  tokensUsed: number
  tokensLimit: number
  onSignOut: () => void
}

export function ChatHeader({ identity, tokensUsed, tokensLimit, onSignOut }: ChatHeaderProps) {
  const percent = tokensLimit > 0 ? Math.min(100, Math.round((tokensUsed / tokensLimit) * 100)) : 0
  const initials = identity.name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .toUpperCase()

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 bg-header px-8 py-3.5 text-white">
      <div className="flex items-center gap-2.5">
        <ShieldLogo color="#8FB3FF" />
        <span className="text-[17px] font-semibold">Control Layer</span>
      </div>
      <div className="flex flex-wrap items-center gap-6">
        <div className="flex min-w-[180px] flex-col gap-1.5">
          <span className="text-xs text-header-muted">
            Budget · {tokensUsed.toLocaleString()} / {tokensLimit.toLocaleString()} tokens
          </span>
          <div className="h-1.5 rounded-full bg-header-chip">
            <div className="h-1.5 rounded-full bg-header-accent" style={{ width: `${percent}%` }} />
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <Avatar sub={identity.sub} initials={initials} size={36} />
          <span className="flex flex-col">
            <span className="text-sm font-medium">{identity.name}</span>
            <span className="text-xs text-header-muted">
              {roleLabel(identity.role)} · {identity.region}
            </span>
          </span>
        </div>
        <button type="button" onClick={onSignOut} className="text-sm text-header-muted hover:text-white">
          Sign out
        </button>
      </div>
    </header>
  )
}
