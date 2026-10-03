import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { AdminHeader } from './AdminHeader'
import { LiveFeed } from '../../pages/LiveFeed'
import { Policy } from '../../pages/Policy'
import { Chat } from '../../pages/Chat'
import { renderWithProviders } from '../../test/renderWithProviders'
import { MockEventSource } from '../../test/mockEventSource'
import { server } from '../../test/server'
import { CONTROL_LAYER_URL } from '../../api/client'
import { saveSession } from '../../lib/session'
import { encodeMockToken } from '../../test/mockAuth'

beforeEach(() => {
  MockEventSource.reset()
  vi.stubGlobal('EventSource', MockEventSource)
})

describe('protection control', () => {
  it('switches to monitor without confirmation', async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, 'confirm')
    renderWithProviders(<AdminHeader />, { route: '/admin' })

    const enforce = await screen.findByRole('button', { name: 'Enforce' })
    await waitFor(() => expect(enforce).toHaveAttribute('aria-pressed', 'true'))

    await user.click(screen.getByRole('button', { name: 'Monitor' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Monitor' })).toHaveAttribute('aria-pressed', 'true'),
    )
    expect(confirm).not.toHaveBeenCalled()
  })

  it('asks for confirmation before turning protection off', async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    renderWithProviders(<AdminHeader />, { route: '/admin' })

    const off = await screen.findByRole('button', { name: 'Off' })
    await waitFor(() => expect(off).toBeEnabled())

    await user.click(off)
    expect(confirm).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Enforce' })).toHaveAttribute('aria-pressed', 'true')

    await user.click(off)
    await waitFor(() => expect(off).toHaveAttribute('aria-pressed', 'true'))
    expect(confirm).toHaveBeenCalledTimes(2)
  })
})

describe('model selector', () => {
  it('lists the available models and switches the active one with a warning when not allowlisted', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AdminHeader />, { route: '/admin' })

    const select = await screen.findByLabelText('Model')
    expect(screen.getByRole('option', { name: /ollama \/ qwen2\.5:7b .* allowed/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /gemma4:latest .* not allowlisted/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /mock \/ mock/ })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    await user.selectOptions(select, 'ollama|gemma4:latest')

    expect(await screen.findByRole('alert')).toHaveTextContent(/Not allowlisted/)
    expect(screen.getByLabelText('Model')).toHaveValue('ollama|gemma4:latest')
  })
})

describe('clear logs', () => {
  it('calls POST /api/logs/clear', async () => {
    const user = userEvent.setup()
    let called = 0
    server.use(
      http.post(`${CONTROL_LAYER_URL}/api/logs/clear`, () => {
        called += 1
        return HttpResponse.json({ ok: true, cleared: ['audit'] })
      }),
    )
    renderWithProviders(<LiveFeed />, { route: '/admin' })

    await user.click(await screen.findByRole('button', { name: 'Clear logs' }))

    await waitFor(() => expect(called).toBe(1))
  })
})

describe('policy rule overrides', () => {
  it('sends PATCH on toggle, shows the overridden badge and clears overrides', async () => {
    const user = userEvent.setup()
    let patched: { enabled?: boolean } | null = null
    server.use(
      http.patch(`${CONTROL_LAYER_URL}/api/policy/rules/pii_masking`, async ({ request }) => {
        patched = (await request.json()) as { enabled: boolean }
        return HttpResponse.json({ rule_id: 'pii_masking', enabled: false, overridden: true })
      }),
    )
    renderWithProviders(<Policy />, { route: '/admin/policy' })

    const toggle = await screen.findByRole('switch', { name: 'Toggle pii_masking' })
    expect(screen.queryByText('overridden')).not.toBeInTheDocument()
    await user.click(toggle)

    await waitFor(() => expect(patched).toEqual({ enabled: false }))
  })

  it('reflects overrides from the server and clears them', async () => {
    const user = userEvent.setup()
    await fetch(`${CONTROL_LAYER_URL}/api/policy/rules/rate_limit`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: false }),
    })
    renderWithProviders(<Policy />, { route: '/admin/policy' })

    expect(await screen.findByText('overridden')).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Toggle rate_limit' })).not.toBeChecked()
    expect(await screen.findByTestId('protection-badge')).toHaveTextContent('Protection: Enforce')

    await user.click(screen.getByRole('button', { name: 'Clear overrides' }))

    await waitFor(() => expect(screen.queryByText('overridden')).not.toBeInTheDocument())
    expect(screen.getByRole('switch', { name: 'Toggle rate_limit' })).toBeChecked()
  })
})

describe('chat protection banner', () => {
  it.each([
    ['monitor', 'monitoring only'],
    ['off', 'protection off'],
  ])('shows the %s banner from /v1/me', async (mode, text) => {
    await fetch(`${CONTROL_LAYER_URL}/api/protection`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    })
    const claims = {
      sub: 'anna.kowalska',
      name: 'Anna Kowalska',
      role: 'developer' as const,
      location: 'Krakow, PL',
      region: 'PL',
    }
    saveSession({ token: encodeMockToken(claims), identity: claims })
    renderWithProviders(<Chat />, { route: '/chat' })

    expect(await screen.findByText(text)).toBeInTheDocument()
  })
})
