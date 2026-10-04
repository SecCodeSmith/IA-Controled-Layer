import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { StageStrip } from './StageStrip'
import {
  PROJECTION_TRACE_FIXTURE,
  PROMPT_TRACE_FIXTURE,
  SHORT_CIRCUIT_TRACE_FIXTURE,
} from '../../test/workbenchFixtures'
import type { TraceStage } from '../../types/workbench'

describe('StageStrip', () => {
  it('shows one idle row of seven placeholders before any trace', () => {
    render(<StageStrip stages={null} />)

    const items = within(screen.getByRole('list', { name: 'Pipeline stages' })).getAllByRole('listitem')
    expect(items).toHaveLength(7)
    expect(screen.queryByText('skipped')).not.toBeInTheDocument()
  })

  it('keeps a single unlabeled row for prompt traces', () => {
    render(<StageStrip stages={PROMPT_TRACE_FIXTURE.stages} />)

    expect(screen.getAllByRole('list')).toHaveLength(1)
    expect(screen.getByRole('list', { name: 'Pipeline stages' })).toBeInTheDocument()
    expect(screen.queryByText('tool_call pass')).not.toBeInTheDocument()
  })

  it('renders one row per pass for a tool call that reached the result stage', () => {
    render(<StageStrip stages={PROJECTION_TRACE_FIXTURE.stages} />)

    const callPass = screen.getByRole('list', { name: 'tool_call pass' })
    const resultPass = screen.getByRole('list', { name: 'tool_result pass' })
    expect(within(callPass).getAllByRole('listitem')).toHaveLength(7)
    expect(within(resultPass).getAllByRole('listitem')).toHaveLength(7)
    expect(screen.getByText('tool_call pass')).toBeVisible()
    expect(screen.getByText('tool_result pass')).toBeVisible()

    const projection = within(resultPass).getByTestId('stage-tool_result-authorization')
    expect(within(projection).getByText('mask')).toBeInTheDocument()
    expect(within(projection).getByText('resource_projection')).toBeInTheDocument()
    expect(within(callPass).getByTestId('stage-tool_call-authorization')).not.toHaveTextContent('mask')
    expect(screen.queryByText('skipped')).not.toBeInTheDocument()
  })

  it('shows only the tool_call pass when the call was blocked and marks missing stages skipped', () => {
    const blocked: TraceStage[] = SHORT_CIRCUIT_TRACE_FIXTURE.stages.map((stage) => ({
      ...stage,
      point: 'tool_call',
    }))
    render(<StageStrip stages={blocked} />)

    expect(screen.queryByRole('list', { name: 'tool_result pass' })).not.toBeInTheDocument()
    const callPass = screen.getByRole('list', { name: 'tool_call pass' })
    expect(within(callPass).getAllByText('skipped')).toHaveLength(4)
  })
})
