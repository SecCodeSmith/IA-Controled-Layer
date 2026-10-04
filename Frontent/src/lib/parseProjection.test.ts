import { describe, expect, it } from 'vitest'
import { parseProjection } from './parseProjection'
import type { TraceStage, TraceViolation } from '../types/workbench'

function stageWith(violation: Partial<TraceViolation>): TraceStage {
  return {
    stage: 'authorization',
    action: 'mask',
    timing_ms: 1,
    cache_hit: false,
    violations: [
      { rule_id: 'resource_projection', action: 'mask', confidence: 1, reason: null, evidence: [], ...violation },
    ],
  }
}

describe('parseProjection', () => {
  it('reads filtered rows and redacted columns from the reason', () => {
    const summary = parseProjection([
      stageWith({ reason: '2 row(s) filtered, 2 column(s) redacted: salary, ssn' }),
    ])

    expect(summary).toEqual({ columnsRedacted: ['salary', 'ssn'], rowsFiltered: 2 })
  })

  it('prefers the structured evidence entries over the reason text', () => {
    const summary = parseProjection([
      stageWith({
        reason: '9 row(s) filtered, 9 column(s) redacted: other',
        evidence: ['resource:hr_directory_rows', 'rows_filtered:2', 'column_redacted:salary', 'column_redacted:ssn'],
      }),
    ])

    expect(summary).toEqual({ columnsRedacted: ['salary', 'ssn'], rowsFiltered: 2 })
  })

  it('reads a reason without the column suffix', () => {
    const summary = parseProjection([stageWith({ reason: '3 row(s) filtered, 0 column(s) redacted' })])

    expect(summary).toEqual({ columnsRedacted: [], rowsFiltered: 3 })
  })

  it('returns null when no projection violation exists', () => {
    expect(parseProjection([stageWith({ rule_id: 'resource_scope' })])).toBeNull()
  })
})
