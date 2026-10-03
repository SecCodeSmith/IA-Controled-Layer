export interface MetaItem {
  label: string
  value: string
}

export function MetaGrid({ items }: { items: MetaItem[] }) {
  return (
    <section className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-x-6 gap-y-4.5 rounded-[10px] border border-border bg-white px-6 py-5">
      {items.map((item) => (
        <div key={item.label} className="flex flex-col gap-1">
          <span className="text-xs uppercase tracking-wide text-muted">{item.label}</span>
          <span className="text-[15px] font-medium">{item.value}</span>
        </div>
      ))}
    </section>
  )
}
