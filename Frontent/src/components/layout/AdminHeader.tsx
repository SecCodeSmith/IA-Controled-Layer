import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import { ShieldLogo } from '../common/ShieldLogo'
import { ProtectionControl } from './ProtectionControl'
import { ModelSelector } from './ModelSelector'

const NAV_ITEMS = [
  { to: '/admin', label: 'Live feed', end: true },
  { to: '/admin/audit', label: 'Audit log', end: false },
  { to: '/admin/policy', label: 'Policy', end: false },
  { to: '/admin/workbench', label: 'Workbench', end: false },
  { to: '/admin/reports', label: 'Reports', end: false },
]

function navLinkClassName({ isActive }: { isActive: boolean }): string {
  return isActive
    ? 'border-b-2 border-header-accent pb-1 font-semibold text-white'
    : 'pb-1 text-header-muted hover:text-white'
}

export function AdminHeader({ actions }: { actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 bg-header px-8 py-3.5 text-white">
      <div className="flex flex-wrap items-center gap-7">
        <div className="flex items-center gap-2.5">
          <ShieldLogo color="#8FB3FF" />
          <span className="text-[17px] font-semibold">Control Layer</span>
          <span className="rounded bg-header-chip px-2 py-0.5 text-xs text-header-muted">Admin</span>
        </div>
        <nav className="flex flex-wrap gap-5 text-sm" aria-label="Admin">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClassName}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <ProtectionControl />
        <ModelSelector />
        {actions}
      </div>
    </header>
  )
}
