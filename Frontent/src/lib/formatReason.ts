interface ReasonLike {
  stage?: string | null
  rule_id?: string | null
  reason: string
}

export function formatReason(row: ReasonLike): string {
  if (row.stage && row.rule_id) {
    return `${row.stage} · ${row.rule_id} — ${row.reason}`
  }
  return row.reason
}
