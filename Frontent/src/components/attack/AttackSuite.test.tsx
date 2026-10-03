import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
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

    expect(await screen.findByText(/1 attacks stopped · 0 got through/)).toBeInTheDocument()
    expect(screen.getByText(/0 compliant passed · 0 not\s+attempted · 0 errors/)).toBeInTheDocument()
    expect(screen.getByText('qwen2.5:7b via ollama · protection enforce · agent tier scripted')).toBeInTheDocument()
    expect(screen.getByText(/STOPPED attack blocked · SUCCEEDED attack got through/)).toBeInTheDocument()
  })

  it('shows running and pending counts only while the run is incomplete', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Run attack suite' }))
    expect(await screen.findByText(/0 running · 10 pending/)).toBeInTheDocument()
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

    const ids = (await (await fetch(`${CONTROL_LAYER_URL}/api/attack-suite/scenarios`)).json()).scenarios.map(
      (scenario: { id: string }) => scenario.id,
    )
    const source = MockEventSource.latest()
    act(() => {
      ids.forEach((id: string, index: number) => {
        source?.emit('scenario', {
          id,
          status: 'STOPPED',
          observed: null,
          duration_ms: index === 0 ? 61 : 6000,
          via: 'scripted',
        })
      })
    })

    await waitFor(() => expect(screen.getAllByTestId('scenario-duration')[0]).toHaveTextContent('61 ms'))
    expect(screen.getAllByTestId('scenario-duration')[1]).toHaveTextContent('6 s')
    expect(screen.getByText('run time 54.06 s')).toBeInTheDocument()
  })
})
