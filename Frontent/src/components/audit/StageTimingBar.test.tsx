import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StageTimingBar } from './StageTimingBar'

describe('StageTimingBar', () => {
  it('renders every stage when all timings are present', () => {
    render(
      <StageTimingBar
        stages={{ identity: 1, authorization: 2, dlp: 3, policy: 4, behavior: 5, resource: 6, audit: 7 }}
      />,
    )

    expect(screen.getByText(/policy · 4 ms/)).toBeInTheDocument()
    expect(screen.getByText(/audit · 7 ms/)).toBeInTheDocument()
  })

  it('shows stages that did not run as skipped instead of crashing', () => {
    render(<StageTimingBar stages={{ identity: 0.5, authorization: 1.5, audit: 0.1 }} />)

    expect(screen.getByText(/authorization · 1.5 ms/)).toBeInTheDocument()
    expect(screen.getByText(/dlp · skipped/)).toBeInTheDocument()
    expect(screen.getByText(/resource · skipped/)).toBeInTheDocument()
  })

  it('renders an empty bar when no timings exist', () => {
    render(<StageTimingBar stages={{}} />)

    expect(screen.getByRole('img', { name: 'Per-stage timing' })).toBeInTheDocument()
    expect(screen.getAllByText(/skipped/)).toHaveLength(7)
  })
})
