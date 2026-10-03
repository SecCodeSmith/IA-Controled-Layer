import { ToolIcon } from '../common/ToolIcon'
import { roleLabel, regionName } from '../../lib/roleLabel'
import { mcpServerLabel } from '../../lib/mcpServerLabels'
import type { ToolDescriptor } from '../../types/identity'

interface ToolsSidebarProps {
  tools: ToolDescriptor[]
  role: string
  region: string
}

interface ServerGroup {
  server: string
  label: string
  scope: string
}

function groupByServer(tools: ToolDescriptor[]): ServerGroup[] {
  const servers = new Map<string, ToolDescriptor[]>()
  for (const tool of tools) {
    const existing = servers.get(tool.server) ?? []
    existing.push(tool)
    servers.set(tool.server, existing)
  }
  return Array.from(servers.entries()).map(([server, serverTools]) => ({
    server,
    label: mcpServerLabel(server),
    scope: aggregateScope(serverTools),
  }))
}

function aggregateScope(tools: ToolDescriptor[]): string {
  const hasDestructive = tools.some((tool) => tool.tags.includes('destructive'))
  const hasWrite = tools.some((tool) => tool.scope.includes('write'))
  if (hasDestructive) return 'read · write*'
  if (hasWrite) return 'read · write'
  return 'read'
}

export function ToolsSidebar({ tools, role, region }: ToolsSidebarProps) {
  const groups = groupByServer(tools)

  return (
    <section className="flex flex-col gap-3.5 rounded-[10px] border border-border bg-white p-5">
      <div className="flex flex-col gap-1">
        <h2 className="text-base font-semibold">Your agent&apos;s tools</h2>
        <span className="text-[13px] text-muted">
          Provisioned for {roleLabel(role)} · {regionName(region)}
        </span>
      </div>
      <div className="flex flex-col">
        {groups.map((group) => (
          <div
            key={group.server}
            className="flex items-center justify-between gap-2.5 border-t border-border-soft py-2.5 first:border-t-0"
          >
            <span className="flex items-center gap-2.5">
              <ToolIcon />
              <span className="text-sm font-medium">{group.label}</span>
            </span>
            <span className="font-mono text-xs text-muted">{group.scope}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
