import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LiveFeed } from './LiveFeed'
import { renderWithProviders } from '../test/renderWithProviders'
import { MockEventSource } from '../test/mockEventSource'

beforeEach(() => {
  MockEventSource.reset()
  vi.stubGlobal('EventSource', MockEventSource)
})

describe('LiveFeed', () => {
  it('renders KPI cards and feed rows from the initial fetch', async () => {
    renderWithProviders(<LiveFeed />, { route: '/admin' })

    expect(await screen.findByText('148')).toBeInTheDocument()
    expect(screen.getByText('Total calls')).toBeInTheDocument()
    expect(screen.getByText('112')).toBeInTheDocument()

    expect(await screen.findByText('github.delete_branch')).toBeInTheDocument()
    expect(screen.getByText('ci.get_run')).toBeInTheDocument()
  })

  it('filters rows by user', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LiveFeed />, { route: '/admin' })

    await screen.findByText('ci.get_run')

    const userSelect = screen.getByLabelText('User')
    await user.selectOptions(userSelect, 'Marek Nowak')

    const table = screen.getByRole('table')
    expect(within(table).queryByText('ci.get_run')).not.toBeInTheDocument()
    expect(within(table).getByText('calendar.list')).toBeInTheDocument()
  })

  it('appends a row when an SSE feed event arrives', async () => {
    renderWithProviders(<LiveFeed />, { route: '/admin' })
    await screen.findByText('ci.get_run')

    const source = MockEventSource.latest()
    expect(source).toBeDefined()

    act(() => {
      source?.emit('feed', {
        call_id: 'c_000999',
        time: '2026-10-03T10:50:00Z',
        user: { sub: 'anna.kowalska', name: 'Anna Kowalska', role: 'developer' },
        kind: 'tool_call',
        target: 'jira.search',
        status: 'ALLOWED',
        stage: null,
        rule_id: null,
        reason: 'Matches roles.developer',
      })
    })

    await waitFor(() => expect(screen.getByText('jira.search')).toBeInTheDocument())
  })

  it('shows the added delay with total and upstream time in the tooltip', async () => {
    renderWithProviders(<LiveFeed />, { route: '/admin' })

    const row = (await screen.findByText('github.delete_branch')).closest('tr')
    expect(screen.getByText('Added delay')).toBeInTheDocument()
    const cell = within(row as HTMLElement).getByText('+3.2 ms')
    expect(cell).toHaveAttribute('title', 'total 3.2 ms · upstream 31 ms')
  })

  it('shows the added delay percentiles computed as proxy minus upstream', async () => {
    renderWithProviders(<LiveFeed />, { route: '/admin' })
    expect(await screen.findByTestId('added-delay-kpi')).toHaveTextContent('Added delay p50 4.1 ms · p95 9.8 ms')
  })

  it('renders a row with kind workbench', async () => {
    renderWithProviders(<LiveFeed />, { route: '/admin' })
    await screen.findByText('ci.get_run')

    act(() => {
      MockEventSource.latest()?.emit('feed', {
        call_id: 'c_000998',
        time: '2026-10-03T10:51:00Z',
        user: { sub: 'anna.kowalska', name: 'Anna Kowalska', role: 'developer' },
        kind: 'workbench',
        target: 'workbench:prompt',
        status: 'FLAGGED',
        stage: 'policy',
        rule_id: 'llm_judge',
        reason: 'Judge confirmed prompt injection',
      })
    })

    const row = (await screen.findByText('workbench:prompt')).closest('tr') as HTMLElement
    expect(within(row).getByText('FLAGGED')).toBeInTheDocument()
  })
})
