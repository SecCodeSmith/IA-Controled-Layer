import type { ProviderInfo } from '../../types/common'

export function ProviderBadge({ provider }: { provider: ProviderInfo }) {
  return (
    <section className="flex flex-col gap-1.5 rounded-[10px] border border-border bg-white px-5 py-4">
      <span className="text-[13px] text-muted">Model</span>
      <span className="font-mono text-[13px]">
        {provider.name} · {provider.model}
      </span>
    </section>
  )
}
