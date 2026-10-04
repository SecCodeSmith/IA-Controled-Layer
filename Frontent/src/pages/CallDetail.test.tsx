import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { CallDetail } from './CallDetail'
import { server } from '../test/server'
import { CONTROL_LAYER_URL } from '../api/client'
import { CALL_DETAIL_FIXTURE } from '../test/fixtures'
import { renderWithProviders } from '../test/renderWithProviders'

describe('CallDetail', () => {
  it('shows the raw response next to the delivered (masked) response', async () => {
    renderWithProviders(<CallDetail />, {
      route: '/admin/audit/c_000139',
      path: '/admin/audit/:callId',
    })

    expect(await screen.findByText('Before masking (admin only)')).toBeInTheDocument()
    expect(screen.getByText(/t\.lis@example\.com/)).toBeInTheDocument()

    expect(screen.getByText('Sent to agent')).toBeInTheDocument()
    expect(screen.getByText(/\[EMAIL_1\]/)).toBeInTheDocument()
    expect(screen.queryByText(/t\.lis@example\.com/)?.closest('pre')).not.toBe(
      screen.queryByText(/\[EMAIL_1\]/)?.closest('pre'),
    )
  })

  it('renders the per-stage timing bar in pipeline order', async () => {
    renderWithProviders(<CallDetail />, {
      route: '/admin/audit/c_000139',
      path: '/admin/audit/:callId',
    })

    await screen.findByText('Per-stage timing')

    const labels = screen.getAllByText(/identity|authorization|dlp|policy|behavior|resource|audit/i, {
      selector: 'span',
    })
    const stageOrder = labels.map((el) => el.textContent?.split(' ')[0])
    expect(stageOrder).toEqual(['identity', 'authorization', 'dlp', 'policy', 'behavior', 'resource', 'audit'])
  })

  it('renders the matched rule YAML and meta grid', async () => {
    renderWithProviders(<CallDetail />, {
      route: '/admin/audit/c_000139',
      path: '/admin/audit/:callId',
    })

    expect(await screen.findByText('Matched rule')).toBeInTheDocument()
    expect(screen.getByText(/id: pii_masking/)).toBeInTheDocument()
    expect(screen.getByText('Anna Kowalska')).toBeInTheDocument()
    expect(screen.getByText('MASKED')).toBeInTheDocument()
    expect(screen.getByText('Added delay')).toBeInTheDocument()
    expect(screen.getByText('+2.4 ms')).toBeInTheDocument()
  })

  it('shows how many placeholders were restored from the session vault, including 0, and hides it when absent', async () => {
    renderWithProviders(<CallDetail />, { route: '/admin/audit/c_000139', path: '/admin/audit/:callId' })
    expect(await screen.findByText('Restored from session vault')).toBeInTheDocument()
    expect(screen.getByText('Restored from session vault').nextElementSibling).toHaveTextContent('2')
  })

  it.each([
    [0, true],
    [undefined, false],
  ])('restored=%s renders the field: %s', async (restored, visible) => {
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/audit/:callId`, () =>
        HttpResponse.json({ ...CALL_DETAIL_FIXTURE, items_restored: restored }),
      ),
    )
    renderWithProviders(<CallDetail />, { route: '/admin/audit/c_000139', path: '/admin/audit/:callId' })
    await screen.findByText('Items masked')
    expect(screen.queryByText('Restored from session vault') !== null).toBe(visible)
  })
})
