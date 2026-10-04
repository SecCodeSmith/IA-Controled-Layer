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

  it('falls back to the evidence lines', () => {
    const summary = parseProjection([
      stageWith({ evidence: ['1 row(s) filtered', '1 column(s) redacted: salary'] }),
    ])

    expect(summary).toEqual({ columnsRedacted: ['salary'], rowsFiltered: 1 })
  })

  it('returns null when no projection violation exists', () => {
    expect(parseProjection([stageWith({ rule_id: 'resource_scope' })])).toBeNull()
  })
})
