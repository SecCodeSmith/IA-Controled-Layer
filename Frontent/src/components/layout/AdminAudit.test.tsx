import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { AdminHeader } from './AdminHeader'
import { LiveFeed } from '../../pages/LiveFeed'
import { AuditLog } from '../../pages/AuditLog'
import { CallDetail } from '../../pages/CallDetail'
import { Chat } from '../../pages/Chat'
import { renderWithProviders } from '../../test/renderWithProviders'
import { MockEventSource } from '../../test/mockEventSource'
import { server } from '../../test/server'
import { CONTROL_LAYER_URL } from '../../api/client'
import { CALL_DETAIL_FIXTURE } from '../../test/fixtures'
import { saveSession } from '../../lib/session'
import { encodeMockToken } from '../../test/mockAuth'
import { formatClock } from '../../lib/clock'

beforeEach(() => {
  MockEventSource.reset()
  vi.stubGlobal('EventSource', MockEventSource)
})

describe('admin audit rows', () => {
  it('marks admin rows in the live feed with an ADMIN chip and lets the role filter select them', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LiveFeed />, { route: '/admin' })

    const target = await screen.findByText('admin.protection')
    const row = target.closest('tr') as HTMLElement
    expect(within(row).getByText('ADMIN')).toBeInTheDocument()
    expect(within(row).getByText('FLAGGED')).toBeInTheDocument()
    expect(screen.getAllByText('ADMIN')).toHaveLength(1)

    await user.selectOptions(screen.getByLabelText('Role'), 'Admin')
    expect(screen.getByText('admin.protection')).toBeInTheDocument()
    expect(screen.queryByText('ci.get_run')).not.toBeInTheDocument()
  })

  it('marks admin rows in the audit log', async () => {
    renderWithProviders(<AuditLog />, { route: '/admin/audit' })
    const row = (await screen.findByText('admin.protection')).closest('tr') as HTMLElement
    expect(within(row).getByText('ADMIN')).toBeInTheDocument()
  })

  it('shows only the reason on the call detail of an admin action', async () => {
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/audit/:callId`, () =>
        HttpResponse.json({
          ...CALL_DETAIL_FIXTURE,
          kind: 'admin',
          target: 'admin.protection',
          matched_rule_yaml: null,
          decision: {
            status: 'FLAGGED',
            stage: null,
            rule_id: null,
            reason: 'protection mode set to off (was enforce)',
            owasp: [],
          },
        }),
      ),
    )
    renderWithProviders(<CallDetail />, { route: '/admin/audit/c_000149', path: '/admin/audit/:callId' })

    expect(await screen.findByText('protection mode set to off (was enforce)')).toBeInTheDocument()
    expect(screen.queryByText('Request')).not.toBeInTheDocument()
    expect(screen.queryByText('Response')).not.toBeInTheDocument()
  })
})

describe('protection changed-at text', () => {
  it('shows when and by whom the protection mode was changed in the admin header', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminHeader />, { route: '/admin' })

    await waitFor(() => expect(screen.getByRole('button', { name: 'Monitor' })).toBeEnabled())
    expect(screen.queryByText(/changed \d\d:\d\d by/)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Monitor' }))

    expect(await screen.findByText(/^changed \d\d:\d\d by admin$/)).toBeInTheDocument()
  })

  it('adds "since HH:MM" to the chat banner', async () => {
    const changedAt = '2026-10-03T09:05:00Z'
    server.use(
      http.get(`${CONTROL_LAYER_URL}/v1/me`, () =>
        HttpResponse.json({
          identity: { sub: 'anna.kowalska', name: 'Anna Kowalska', role: 'developer', location: 'Krakow, PL', region: 'PL' },
          tools: [],
          policy: { name: 'roles.developer', version: 3 },
          budget: { tokens_used: 1, tokens_limit: 10, cost_used_usd: 0, cost_limit_usd: 1, resets_at: '2026-10-05T00:00:00Z' },
          risk: { score: 1, level: 'low' },
          provider: { name: 'ollama', model: 'qwen2.5:7b' },
          protection: { mode: 'monitor', changed_at: changedAt, changed_by: 'admin' },
        }),
      ),
    )
    const claims = {
      sub: 'anna.kowalska',
      name: 'Anna Kowalska',
      role: 'developer' as const,
      location: 'Krakow, PL',
      region: 'PL',
    }
    saveSession({ token: encodeMockToken(claims), identity: claims })
    renderWithProviders(<Chat />, { route: '/chat' })

    expect(await screen.findByText(`· since ${formatClock(changedAt)}`)).toBeInTheDocument()
    expect(screen.getByText('monitoring only')).toBeInTheDocument()
  })
})
