import type { ReactNode } from 'react'

interface WorkbenchCardProps {
  title: string
  subtitle?: string
  children: ReactNode
}

export function WorkbenchCard({ title, subtitle, children }: WorkbenchCardProps) {
  return (
    <section className="flex flex-col gap-4 rounded-[10px] border border-border bg-white px-6 py-5">
      <div className="flex flex-col gap-1">
        <h2 className="m-0 text-[17px] font-semibold">{title}</h2>
        {subtitle ? <span className="text-[13px] text-muted">{subtitle}</span> : null}
      </div>
      {children}
    </section>
  )
}
