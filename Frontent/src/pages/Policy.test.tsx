import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { Policy } from './Policy'
import { renderWithProviders } from '../test/renderWithProviders'
import { server } from '../test/server'
import { CONTROL_LAYER_URL } from '../api/client'
import { POLICY_FIXTURE } from '../test/fixtures'

describe('Policy', () => {
  it('shows the LOADED status, raw YAML and rules grouped in pipeline stage order', async () => {
    renderWithProviders(<Policy />, { route: '/admin/policy' })

    expect(await screen.findByText('LOADED')).toBeInTheDocument()
    expect(screen.getByText(/policy\.yaml · v3/)).toBeInTheDocument()
    expect(screen.getByText(/profile: balanced/)).toBeInTheDocument()

    const headings = screen.getAllByRole('heading', { level: 3 })
    const headingOrder = headings.map((heading) => heading.textContent)
    expect(headingOrder).toEqual(['authorization', 'dlp', 'policy', 'behavior'])

    expect(screen.getByText('pii_masking')).toBeInTheDocument()
    expect(screen.getByText('role_provisioning')).toBeInTheDocument()
  })

  it('shows the ERROR status and the error message when the policy fails to load', async () => {
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/policy`, () =>
        HttpResponse.json({
          ...POLICY_FIXTURE,
          status: 'ERROR',
          error: 'YAML parse error at line 12: mapping values are not allowed here',
        }),
      ),
    )

    renderWithProviders(<Policy />, { route: '/admin/policy' })

    expect(await screen.findByText('ERROR')).toBeInTheDocument()
    expect(screen.getByText(/YAML parse error at line 12/)).toBeInTheDocument()
  })
})
