export interface OwaspCoverageItem {
  id: string
  title: string
  events: number
  status: string
}

export interface SecurityReport {
  generated_at: string
  period: string
  summary: Record<string, unknown>
  top_rules: unknown[]
  top_users: unknown[]
  owasp_coverage: OwaspCoverageItem[]
  recommendations: string[]
  markdown: string
}
