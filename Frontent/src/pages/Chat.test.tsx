import { beforeEach, describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Chat } from './Chat'
import { renderWithProviders } from '../test/renderWithProviders'
import { saveSession } from '../lib/session'
import { encodeMockToken } from '../test/mockAuth'

const ANNA_CLAIMS = {
  sub: 'anna.kowalska',
  name: 'Anna Kowalska',
  role: 'developer' as const,
  location: 'Krakow, PL',
  region: 'PL',
  agent_id: 'agent-anna-dev-7f3a',
}

function signInAsAnna() {
  saveSession({
    token: encodeMockToken(ANNA_CLAIMS),
    identity: ANNA_CLAIMS,
  })
}

describe('Chat', () => {
  beforeEach(() => {
    signInAsAnna()
  })

  it('shows the budget header and provisioned tools from /v1/me', async () => {
    renderWithProviders(<Chat />, { route: '/chat' })

    expect(await screen.findByText(/Budget · 3,420 \/ 10,000 tokens/)).toBeInTheDocument()
    expect(screen.getByText("Your agent's tools")).toBeInTheDocument()
    expect(screen.getByText('GitHub')).toBeInTheDocument()
  })

  it('renders tool-call cards with statuses and reasons for a scripted reply', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Chat />, { route: '/chat' })

    await screen.findByText("Your agent's tools")

    const input = screen.getByPlaceholderText('Ask about code, CI, logs or tickets…')
    await user.type(input, 'Why did the login tests fail last night?')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('ci.get_run(pipeline="e2e-login", date="2026-10-02")')).toBeInTheDocument()
    expect(screen.getByText('ALLOWED')).toBeInTheDocument()

    expect(screen.getByText('logs-db.query(service="auth", since="24h")')).toBeInTheDocument()
    expect(screen.getByText('MASKED')).toBeInTheDocument()
    expect(screen.getByText(/3 email addresses masked in the response · rule pii_masking/)).toBeInTheDocument()

    expect(screen.getByText('hr-db.find_approver(request="test-accounts")')).toBeInTheDocument()
    expect(screen.getByText('BLOCKED')).toBeInTheDocument()
    expect(
      screen.getByText(/HR database is not provisioned for the Developer role · rule role_provisioning/),
    ).toBeInTheDocument()

    await waitFor(() => expect(screen.getByText(/Budget · 3,640 \/ 10,000 tokens/)).toBeInTheDocument())
  })

  it('shows an approval card and appends events after approving', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Chat />, { route: '/chat' })

    await screen.findByText("Your agent's tools")

    const input = screen.getByPlaceholderText('Ask about code, CI, logs or tickets…')
    await user.type(input, 'Delete the stale branch feature/old-login.')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('Approval required')).toBeInTheDocument()
    expect(
      screen.getByText(/Destructive actions need your confirmation · rule destructive_requires_approval/),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Approve' }))

    expect(await screen.findByText('Done — the branch has been deleted.')).toBeInTheDocument()
    expect(screen.getAllByText('ALLOWED').length).toBeGreaterThan(0)
  })
})
