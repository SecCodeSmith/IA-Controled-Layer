export function PolicySidebar({ name, version }: { name: string; version: number }) {
  return (
    <section className="flex flex-col gap-1.5 rounded-[10px] border border-border bg-white px-5 py-4">
      <span className="text-[13px] text-muted">Active policy</span>
      <span className="font-mono text-[13px]">
        {name} · v{version}
      </span>
    </section>
  )
}
