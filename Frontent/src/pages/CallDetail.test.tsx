import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { CallDetail } from './CallDetail'
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
  })
})
