import type { TraceStage, TraceViolation } from '../types/workbench'

const PROJECTION_RULE_ID = 'resource_projection'
const ROWS_EVIDENCE_PREFIX = 'rows_filtered:'
const COLUMN_EVIDENCE_PREFIX = 'column_redacted:'
const ROWS_PATTERN = /(\d+) row\(s\) filtered/
const COLUMNS_PATTERN = /column\(s\) redacted: (.+)$/

export interface ProjectionSummary {
  columnsRedacted: string[]
  rowsFiltered: number
}

function evidenceValues(evidence: string[], prefix: string): string[] {
  return evidence.filter((entry) => entry.startsWith(prefix)).map((entry) => entry.slice(prefix.length))
}

function summarizeEvidence(evidence: string[]): ProjectionSummary | null {
  const [rows] = evidenceValues(evidence, ROWS_EVIDENCE_PREFIX)
  if (rows === undefined) return null
  return { columnsRedacted: evidenceValues(evidence, COLUMN_EVIDENCE_PREFIX), rowsFiltered: Number(rows) || 0 }
}

function summarizeReason(reason: string | null): ProjectionSummary {
  const text = reason ?? ''
  const rows = ROWS_PATTERN.exec(text)
  const columns = COLUMNS_PATTERN.exec(text)
  return {
    columnsRedacted: columns ? columns[1].split(',').map((column) => column.trim()).filter(Boolean) : [],
    rowsFiltered: rows ? Number(rows[1]) : 0,
  }
}

function summarize(violation: TraceViolation): ProjectionSummary {
  return summarizeEvidence(violation.evidence) ?? summarizeReason(violation.reason)
}

export function parseProjection(stages: TraceStage[]): ProjectionSummary | null {
  const violation = stages
    .flatMap((stage) => stage.violations)
    .find((candidate) => candidate.rule_id === PROJECTION_RULE_ID)
  return violation ? summarize(violation) : null
}
