import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AttackSuitePanel } from './AttackSuitePanel'
import { MockEventSource } from '../../test/mockEventSource'

beforeEach(() => {
  MockEventSource.reset()
  vi.stubGlobal('EventSource', MockEventSource)
})

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AttackSuitePanel />
    </QueryClientProvider>,
  )
}

describe('AttackSuitePanel', () => {
  it('creates a run and updates scenario statuses from SSE events', async () => {
    const user = userEvent.setup()
    renderPanel()

    await user.click(screen.getByRole('button', { name: 'Run attack suite' }))

    expect(await screen.findByText(/run #1/)).toBeInTheDocument()
    expect(screen.getByText('Developer reads HR database')).toBeInTheDocument()

    const source = MockEventSource.latest()
    expect(source).toBeDefined()

    act(() => {
      source?.emit('scenario', {
        id: 'dev_reads_hr_db',
        status: 'STOPPED',
        observed: { status: 'BLOCKED', stage: 'authorization', rule_id: 'role_provisioning' },
        duration_ms: 142,
      })
    })

    const scenarioRow = screen.getByText('Developer reads HR database').closest('div')
    await waitFor(() => expect(scenarioRow?.textContent).toContain('STOPPED'))

    act(() => {
      source?.emit('run_complete', {
        summary: { stopped: 1, passed: 0, succeeded: 0, not_attempted: 0, running: 0, pending: 9 },
      })
    })

    expect(await screen.findByText(/1 attacks stopped · 0 succeeded/)).toBeInTheDocument()
  })
})
