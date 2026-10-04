import type { TraceStage } from '../types/workbench'

const PROJECTION_RULE_ID = 'resource_projection'
const ROWS_PATTERN = /(\d+) row\(s\) filtered/
const COLUMNS_PATTERN = /column\(s\) redacted: (.+)$/

export interface ProjectionSummary {
  columnsRedacted: string[]
  rowsFiltered: number
}

function parseColumns(text: string): string[] {
  const match = COLUMNS_PATTERN.exec(text)
  return match ? match[1].split(',').map((column) => column.trim()).filter(Boolean) : []
}

function parseRows(text: string): number {
  const match = ROWS_PATTERN.exec(text)
  return match ? Number(match[1]) : 0
}

export function parseProjection(stages: TraceStage[]): ProjectionSummary | null {
  const violation = stages
    .flatMap((stage) => stage.violations)
    .find((candidate) => candidate.rule_id === PROJECTION_RULE_ID)
  if (!violation) return null
  const sources = [violation.reason ?? '', ...violation.evidence]
  return {
    columnsRedacted: sources.map(parseColumns).find((columns) => columns.length > 0) ?? [],
    rowsFiltered: Math.max(0, ...sources.map(parseRows)),
  }
}
