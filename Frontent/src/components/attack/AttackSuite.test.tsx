import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AttackSuitePanel } from './AttackSuitePanel'
import { MockEventSource } from '../../test/mockEventSource'
import { CONTROL_LAYER_URL } from '../../api/client'

async function putAdmin(path: string, body: unknown) {
  await fetch(`${CONTROL_LAYER_URL}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

beforeEach(() => {
  MockEventSource.reset()
  vi.stubGlobal('EventSource', MockEventSource)
})

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AttackSuitePanel />
      </MemoryRouter>
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

    expect(await screen.findByText(/1 attacks stopped · 0 got through/)).toBeInTheDocument()
    expect(screen.getByText(/0 compliant passed · 0 not\s+attempted · 0 errors/)).toBeInTheDocument()
    expect(screen.getByText('qwen2.5:7b via ollama · protection enforce · agent tier scripted')).toBeInTheDocument()
    expect(screen.getByText(/STOPPED attack blocked · SUCCEEDED attack got through/)).toBeInTheDocument()
  })

  it('shows running and pending counts only while the run is incomplete', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Run attack suite' }))
    expect(await screen.findByText(/0 running · 11 pending/)).toBeInTheDocument()
  })

  it('warns before and after a run when protection is not enforce', async () => {
    await putAdmin('/api/protection', { mode: 'off' })
    const user = userEvent.setup()
    renderPanel()

    expect(await screen.findByText(/Protection is off: attacks are expected to get through/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Run attack suite' }))
    expect(await screen.findByText(/protection off · agent tier scripted/)).toBeInTheDocument()
    expect(screen.getByText(/Protection is off: attacks are expected to get through/)).toBeInTheDocument()
  })

  it('warns when the ollama tier is selected but the active provider is not ollama', async () => {
    await putAdmin('/api/models', { provider: 'mock', model: 'mock' })
    const user = userEvent.setup()
    renderPanel()

    expect(screen.queryByText(/needs an Ollama model/)).not.toBeInTheDocument()
    await user.selectOptions(await screen.findByLabelText('Attack suite agent'), 'ollama')
    expect(
      await screen.findByText('Active model is mock (mock); the ollama tier needs an Ollama model. Pick one in the model selector.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/--agent ollama/)).toBeInTheDocument()
  })

  it('marks scenarios driven by the scripted fallback during an ollama run and explains NOT_ATTEMPTED', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.selectOptions(screen.getByLabelText('Attack suite agent'), 'ollama')
    await user.click(screen.getByRole('button', { name: 'Run attack suite' }))
    await screen.findByText(/run #1/)

    const source = MockEventSource.latest()
    act(() => {
      source?.emit('scenario', {
        id: 'spoofed_role_in_request',
        status: 'STOPPED',
        observed: null,
        duration_ms: 5,
        via: 'scripted',
      })
      source?.emit('scenario', {
        id: 'dev_reads_hr_db',
        status: 'NOT_ATTEMPTED',
        observed: null,
        duration_ms: 5,
        via: 'agent',
      })
    })

    await waitFor(() =>
      expect(screen.getAllByText('scripted').some((element) => element.tagName === 'SPAN')).toBe(true),
    )
    expect(screen.getByText('NOT_ATTEMPTED').parentElement).toHaveAttribute(
      'title',
      'the model never attempted the risky action, so the control was not exercised',
    )
  })

  it('shows per-scenario durations and the total run time once the run is complete', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Run attack suite' }))
    await screen.findByText(/run #1/)

    expect(screen.getAllByTestId('scenario-duration')[0]).toHaveTextContent('–')
    const rowOf = (name: string) => screen.getByText(name).closest('div') as HTMLElement

    const ids = (await (await fetch(`${CONTROL_LAYER_URL}/api/attack-suite/scenarios`)).json()).scenarios.map(
      (scenario: { id: string }) => scenario.id,
    )
    const source = MockEventSource.latest()
    act(() => {
      ids.forEach((id: string) => {
        source?.emit('scenario', {
          id,
          status: 'STOPPED',
          observed: null,
          duration_ms: id === 'dev_reads_hr_db' ? 61 : 6000,
          via: 'scripted',
        })
      })
    })

    await waitFor(() =>
      expect(within(rowOf('Developer reads HR database')).getByTestId('scenario-duration')).toHaveTextContent(
        '61 ms',
      ),
    )
    expect(within(rowOf('Direct push to main')).getByTestId('scenario-duration')).toHaveTextContent('6 s')
    expect(screen.getByText('run time 1 min 0 s')).toBeInTheDocument()
  })

  it('lists the catalogue grouped by stage before any run and expands a row to show its steps', async () => {
    const user = userEvent.setup()
    renderPanel()

    const toggle = await screen.findByRole('button', { name: /Developer reads HR database/ })
    expect(screen.getByText(/11 scenarios in the catalogue/)).toBeInTheDocument()
    expect(screen.getByText('authorization')).toBeInTheDocument()
    expect(within(toggle).getByText('PENDING')).toBeInTheDocument()
    expect(toggle).toHaveAttribute('aria-expanded', 'false')

    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('A developer asks the agent for HR data they are not provisioned for.')).toBeInTheDocument()
    expect(screen.getByText('anna.kowalska')).toBeInTheDocument()
    expect(screen.getByText('tool_call hr-db.find_approver {request: test-accounts}')).toBeInTheDocument()

    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('A developer asks the agent for HR data they are not provisioned for.')).not.toBeInTheDocument()
  })

  it('shows positives first within a stage', async () => {
    renderPanel()
    const positive = await screen.findByRole('button', { name: /Developer reads a CI run/ })
    const negative = screen.getByRole('button', { name: /Developer reads HR database/ })
    expect(positive.compareDocumentPosition(negative) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('renders the explanation and the trace with a call link after a run', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Run attack suite' }))
    await screen.findByText(/run #1/)

    act(() => {
      MockEventSource.latest()?.emit('scenario', {
        id: 'dev_reads_hr_db',
        status: 'STOPPED',
        observed: {
          status: 'BLOCKED',
          stage: 'authorization',
          rule_id: 'role_provisioning',
          reason: 'HR database is not provisioned',
        },
        duration_ms: 120,
        via: 'scripted',
        explanation: 'Blocked at authorization by role_provisioning as expected.',
        error: null,
        trace: [
          {
            target: 'hr-db.find_approver',
            status: 'BLOCKED',
            stage: 'authorization',
            rule_id: 'role_provisioning',
            reason: 'HR database is not provisioned',
            call_id: 'c_000042',
            http_status: 403,
          },
        ],
      })
    })

    await user.click(screen.getByRole('button', { name: /Developer reads HR database/ }))
    expect(await screen.findByText('Blocked at authorization by role_provisioning as expected.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'c_000042' })).toHaveAttribute('href', '/admin/audit/c_000042')
    expect(screen.getByText('hr-db.find_approver')).toBeInTheDocument()
  })

  it('shows the error text for ERROR scenarios', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Run attack suite' }))
    await screen.findByText(/run #1/)
    act(() => {
      MockEventSource.latest()?.emit('scenario', {
        id: 'dev_reads_hr_db',
        status: 'ERROR',
        observed: null,
        duration_ms: 5,
        via: 'agent',
        explanation: null,
        error: 'agent service unreachable',
        trace: [],
      })
    })
    await user.click(screen.getByRole('button', { name: /Developer reads HR database/ }))
    expect(await screen.findByText('agent service unreachable')).toBeInTheDocument()
  })

  it('filters the list by status and by name', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Run attack suite' }))
    await screen.findByText(/run #1/)
    act(() => {
      const source = MockEventSource.latest()
      source?.emit('scenario', { id: 'dev_reads_hr_db', status: 'SUCCEEDED', observed: null, duration_ms: 1 })
      source?.emit('scenario', { id: 'direct_push_main', status: 'NOT_ATTEMPTED', observed: null, duration_ms: 1 })
      source?.emit('scenario', { id: 'pii_in_log_response', status: 'STOPPED', observed: null, duration_ms: 1 })
    })

    await user.click(screen.getByRole('button', { name: 'Failed' }))
    expect(screen.getByText('Developer reads HR database')).toBeInTheDocument()
    expect(screen.queryByText('Direct push to main')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Not attempted' }))
    expect(screen.getByText('Direct push to main')).toBeInTheDocument()
    expect(screen.queryByText('Developer reads HR database')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Passed + Stopped' }))
    expect(screen.getByText('PII in log response')).toBeInTheDocument()
    expect(screen.queryByText('Direct push to main')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'All' }))
    await user.type(screen.getByLabelText('Filter scenarios by name'), 'push')
    expect(screen.getByText('Direct push to main')).toBeInTheDocument()
    expect(screen.queryByText('PII in log response')).not.toBeInTheDocument()
  })

  it('copies a plain-text report to the clipboard', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Run attack suite' }))
    await screen.findByText(/run #1/)
    act(() => {
      MockEventSource.latest()?.emit('scenario', {
        id: 'dev_reads_hr_db',
        status: 'STOPPED',
        observed: null,
        duration_ms: 1,
        explanation: 'Blocked at authorization.',
      })
    })

    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await user.click(screen.getByRole('button', { name: 'Copy report' }))

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1))
    const text = writeText.mock.calls[0][0] as string
    expect(text.split('\n')[0]).toBe(
      'Attack suite run #1 · qwen2.5:7b via ollama · protection enforce · agent tier scripted',
    )
    expect(text).toContain('STOPPED · Developer reads HR database — Blocked at authorization.')
    expect(text).toContain('PENDING · Direct push to main')
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeInTheDocument()
  })
})
