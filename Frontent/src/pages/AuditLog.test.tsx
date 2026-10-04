import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { AuditLog } from './AuditLog'
import { renderWithProviders } from '../test/renderWithProviders'
import { server } from '../test/server'
import { CONTROL_LAYER_URL } from '../api/client'
import { AUDIT_LIST_FIXTURE } from '../test/fixtures'

describe('AuditLog', () => {
  it('shows the added delay, falls back to proxy minus upstream, and a dash when missing', async () => {
    const [first, second, third] = AUDIT_LIST_FIXTURE
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/audit`, () =>
        HttpResponse.json({
          items: [
            { ...first, overhead_ms: 2.4, proxy_latency_ms: 814.4, upstream_latency_ms: 812 },
            { ...third, overhead_ms: undefined, proxy_latency_ms: 50, upstream_latency_ms: 30 },
            { ...second, overhead_ms: undefined, proxy_latency_ms: undefined, upstream_latency_ms: undefined },
          ],
        }),
      ),
    )
    renderWithProviders(<AuditLog />, { route: '/admin/audit' })

    expect(await screen.findByText('Added delay')).toBeInTheDocument()
    const filled = within((await screen.findByText(first.target)).closest('tr') as HTMLElement).getByText('+2.4 ms')
    expect(filled).toHaveAttribute('title', 'total 814.4 ms · upstream 812 ms')
    expect(within(screen.getByText(third.target).closest('tr') as HTMLElement).getByText('+20 ms')).toBeInTheDocument()
    const empty = within(screen.getByText(second.target).closest('tr') as HTMLElement).getByText('–')
    expect(empty).not.toHaveAttribute('title')
  })

  it('offers workbench as a kind filter and sends it to the API', async () => {
    const user = userEvent.setup()
    const kinds: Array<string | null> = []
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/audit`, ({ request }) => {
        kinds.push(new URL(request.url).searchParams.get('kind'))
        return HttpResponse.json({ items: [] })
      }),
    )
    renderWithProviders(<AuditLog />, { route: '/admin/audit' })

    await user.selectOptions(await screen.findByLabelText('Kind'), 'workbench')

    await waitFor(() => expect(kinds).toContain('workbench'))
  })
})
