import { useResourceMatrix, WORKBENCH_RESOURCES_PATH } from '../../api/workbench'
import { roleLabel } from '../../lib/roleLabel'
import { summarizeGrant } from '../../lib/summarizeGrant'
import type { ResourceGrantView, ResourceView } from '../../types/workbench'
import { Spinner } from '../common/Spinner'
import { EndpointErrorBanner } from './EndpointErrorBanner'

const DEFAULT_ROLE = '*'

function roleHeading(role: string): string {
  return role === DEFAULT_ROLE ? 'default' : roleLabel(role)
}

function GrantCell({ grant }: { grant: ResourceGrantView | undefined }) {
  if (!grant) return <span className="text-muted">no grant</span>
  const lines = summarizeGrant(grant)
  if (lines.length === 0) return <span className="text-muted">unrestricted</span>
  return (
    <div className="flex flex-col gap-0.5">
      {lines.map((line) => (
        <span key={line} className="font-mono text-xs">
          {line}
        </span>
      ))}
    </div>
  )
}

function resourceTools(resource: ResourceView): string {
  return resource.tools.length > 0
    ? resource.tools.map((tool) => `${resource.server}.${tool}`).join(', ')
    : `${resource.server}.*`
}

export function ResourceMatrix() {
  const matrix = useResourceMatrix()

  if (matrix.isLoading) return <Spinner label="Loading resources…" />
  if (matrix.isError) return <EndpointErrorBanner error={matrix.error} endpoint={WORKBENCH_RESOURCES_PATH} />
  if (!matrix.data) return null

  const { roles, resources } = matrix.data
  if (resources.length === 0) return <p className="m-0 text-sm text-muted">No resources configured.</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-muted">
            <th className="px-3 py-2 font-medium">Resource</th>
            {roles.map((role) => (
              <th key={role} className="px-3 py-2 font-medium">
                {roleHeading(role)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {resources.map((resource) => (
            <tr key={resource.id} className="border-t border-border-soft align-top">
              <td className="px-3 py-2.5">
                <div className="text-[13px] font-semibold">{resource.id}</div>
                <div className="font-mono text-xs text-muted">{resourceTools(resource)}</div>
              </td>
              {roles.map((role) => (
                <td key={role} className="px-3 py-2.5">
                  <GrantCell grant={resource.grants[role]} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
