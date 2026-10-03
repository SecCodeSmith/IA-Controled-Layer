export function StageChip({ stage }: { stage: string }) {
  return (
    <span className="rounded bg-border-soft px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-muted">
      {stage}
    </span>
  )
}
