interface Kpi {
  label: string
  value: number
  color: string
}

export function KpiCards({
  totalCalls,
  allowed,
  blocked,
  masked,
  escalated,
}: {
  totalCalls: number
  allowed: number
  blocked: number
  masked: number
  escalated: number
}) {
  const kpis: Kpi[] = [
    { label: 'Total calls', value: totalCalls, color: '#16181B' },
    { label: 'Allowed', value: allowed, color: '#17613F' },
    { label: 'Blocked', value: blocked, color: '#A3301A' },
    { label: 'Masked', value: masked, color: '#7A4E00' },
    { label: 'Escalated', value: escalated, color: '#2348B8' },
  ]

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-4">
      {kpis.map((kpi) => (
        <div
          key={kpi.label}
          className="flex flex-col gap-1.5 rounded-[10px] border border-border bg-white px-5 py-4.5"
        >
          <span className="text-sm text-muted">{kpi.label}</span>
          <span className="text-[34px] font-semibold tracking-tight" style={{ color: kpi.color }}>
            {kpi.value}
          </span>
        </div>
      ))}
    </div>
  )
}
