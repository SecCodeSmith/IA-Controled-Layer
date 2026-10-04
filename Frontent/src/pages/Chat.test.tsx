import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import userEvent from '@testing-library/user-event'
import { Chat } from './Chat'
import { renderWithProviders } from '../test/renderWithProviders'
import { saveSession } from '../lib/session'
import { encodeMockToken } from '../test/mockAuth'
import { server } from '../test/server'
import { AGENT_URL, CONTROL_LAYER_URL } from '../api/client'

const adminToken = vi.hoisted(() => ({ value: 'admin-dev-token' }))
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  const mod = { ...actual }
  Object.defineProperty(mod, 'ADMIN_TOKEN', { get: () => adminToken.value, enumerable: true })
  return mod
})

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
    adminToken.value = 'admin-dev-token'
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
    const chip = screen.getByText('1 restored')
    expect(chip).toHaveAttribute(
      'title',
      'placeholders restored by the control layer; the model never saw the values',
    )
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

  it('renders the New demo conversation button with its helper text', async () => {
    renderWithProviders(<Chat />, { route: '/chat' })
    await screen.findByText("Your agent's tools")
    expect(screen.getByRole('button', { name: 'New demo conversation' })).toBeEnabled()
    expect(screen.getByText("resets the conversation and this user's limits")).toBeInTheDocument()
  })

  it('New demo conversation resets agent and limits, clears the transcript and rotates the id', async () => {
    const user = userEvent.setup()
    const resetIds: string[] = []
    const demoScopes: Array<string | null> = []
    server.use(
      http.post(`${AGENT_URL}/agent/sessions/:sessionId/reset`, ({ params }) => {
        resetIds.push(String(params.sessionId))
        return HttpResponse.json({ session_id: String(params.sessionId), cleared: true })
      }),
      http.post(`${CONTROL_LAYER_URL}/api/demo/reset`, ({ request }) => {
        demoScopes.push(new URL(request.url).searchParams.get('scope'))
        return HttpResponse.json({ ok: true })
      }),
    )
    renderWithProviders(<Chat />, { route: '/chat' })
    await screen.findByText("Your agent's tools")
    const oldId = sessionStorage.getItem('control-layer.tab-session-id')
    expect(oldId).toBeTruthy()

    await user.type(screen.getByPlaceholderText('Ask about code, CI, logs or tickets…'), 'Why did the login tests fail last night?')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    expect(await screen.findByText('ci.get_run(pipeline="e2e-login", date="2026-10-02")')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'New demo conversation' }))

    expect(await screen.findByText('Fresh conversation started · limits reset')).toBeInTheDocument()
    expect(screen.queryByText('ci.get_run(pipeline="e2e-login", date="2026-10-02")')).not.toBeInTheDocument()
    expect(resetIds).toEqual([oldId])
    expect(demoScopes).toEqual(['behavior'])
    const newId = sessionStorage.getItem('control-layer.tab-session-id')
    expect(newId).toBeTruthy()
    expect(newId).not.toBe(oldId)
    expect(screen.getByText(/Budget · /)).toBeInTheDocument()
  })

  it('skips the demo reset and shows the shorter confirmation when no admin token is configured', async () => {
    const user = userEvent.setup()
    adminToken.value = ''
    let demoCalls = 0
    server.use(
      http.post(`${CONTROL_LAYER_URL}/api/demo/reset`, () => {
        demoCalls += 1
        return HttpResponse.json({ ok: true })
      }),
    )
    renderWithProviders(<Chat />, { route: '/chat' })
    await screen.findByText("Your agent's tools")
    const oldId = sessionStorage.getItem('control-layer.tab-session-id')

    await user.click(screen.getByRole('button', { name: 'New demo conversation' }))

    expect(await screen.findByText('Fresh conversation started')).toBeInTheDocument()
    expect(screen.queryByText(/limits reset/)).not.toBeInTheDocument()
    expect(demoCalls).toBe(0)
    expect(sessionStorage.getItem('control-layer.tab-session-id')).not.toBe(oldId)
  })

  it('still rotates and shows a note when the agent cannot reset', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${AGENT_URL}/agent/sessions/:sessionId/reset`, () =>
        HttpResponse.json({ error: { code: 'not_found', reason: 'nope' } }, { status: 404 }),
      ),
    )
    renderWithProviders(<Chat />, { route: '/chat' })
    await screen.findByText("Your agent's tools")
    const oldId = sessionStorage.getItem('control-layer.tab-session-id')

    await user.click(screen.getByRole('button', { name: 'New demo conversation' }))

    expect(await screen.findByText('previous conversation could not be reset on the agent')).toBeInTheDocument()
    expect(sessionStorage.getItem('control-layer.tab-session-id')).not.toBe(oldId)
  })

  it('renders a memory-cleared notice as a system line, not an assistant bubble', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${AGENT_URL}/agent/chat`, async ({ request }) => {
        const body = (await request.json()) as { session_id: string }
        return HttpResponse.json({
          session_id: body.session_id,
          events: [{ type: 'notice', reason: 'Conversation memory cleared because the user changed' }],
          budget: { tokens_used: 0, tokens_limit: 10000 },
        })
      }),
    )
    renderWithProviders(<Chat />, { route: '/chat' })
    await screen.findByText("Your agent's tools")
    await user.type(screen.getByPlaceholderText('Ask about code, CI, logs or tickets…'), 'hello')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    const line = await screen.findByText(/Conversation memory cleared because the user changed/)
    expect(line).toHaveAttribute('role', 'note')
    expect(screen.queryByText('Agent')).not.toBeInTheDocument()
  })

  it('clears the chat session id on sign-out', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Chat />, { route: '/chat' })
    await screen.findByText("Your agent's tools")
    expect(sessionStorage.getItem('control-layer.tab-session-id')).toBeTruthy()

    await user.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(sessionStorage.getItem('control-layer.tab-session-id')).toBeNull()
  })
})
