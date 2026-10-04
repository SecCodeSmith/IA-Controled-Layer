import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { ResourceSimulator } from './ResourceSimulator'
import { renderWithProviders } from '../../test/renderWithProviders'
import { server } from '../../test/server'
import { CONTROL_LAYER_URL } from '../../api/client'
import { PROJECTION_TRACE_FIXTURE } from '../../test/workbenchFixtures'

async function fillForm(user: ReturnType<typeof userEvent.setup>, args = '{"query": "all"}') {
  await screen.findByRole('option', { name: 'Marek Nowak' })
  await user.selectOptions(screen.getByLabelText('Simulator actor'), 'marek.nowak')
  await user.type(screen.getByLabelText('Server'), 'hr-db')
  await user.type(screen.getByLabelText('Tool'), 'query')
  const textarea = screen.getByLabelText('Arguments (JSON)')
  await user.clear(textarea)
  await user.click(textarea)
  await user.paste(args)
}

const projectionStage = PROJECTION_TRACE_FIXTURE.stages.find((stage) => stage.violations.length > 0)!

describe('ResourceSimulator', () => {
  it('posts a tool_call trace and shows status, raw vs delivered and the redactions', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ResourceSimulator />)

    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Simulate' }))

    expect(await screen.findByText('MASKED')).toBeInTheDocument()
    expect(screen.getByText('authorization · resource_projection')).toBeInTheDocument()

    const raw = screen.getByTestId('raw-result')
    const delivered = screen.getByTestId('delivered-result')
    expect(within(raw).getByText(/"salary": 9000/)).toBeInTheDocument()
    expect(within(raw).getByText(/E-2101/)).toBeInTheDocument()
    expect(within(delivered).queryByText(/salary/)).not.toBeInTheDocument()
    expect(within(delivered).queryByText(/E-2101/)).not.toBeInTheDocument()

    expect(screen.getByText('Redacted columns: salary')).toBeInTheDocument()
    expect(screen.getByText('Rows filtered: 1')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Audit record c_002003' })).toHaveAttribute(
      'href',
      '/admin/audit/c_002003',
    )
  })

  it('sends the actor, server, tool and parsed arguments', async () => {
    const user = userEvent.setup()
    let body: unknown
    server.use(
      http.post(`${CONTROL_LAYER_URL}/api/workbench/trace`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({
          call_id: 'c_9',
          kind: 'workbench',
          status: 'BLOCKED',
          action: 'block',
          stage: 'authorization',
          rule_id: 'resource_scope',
          reason: 'path denied',
          masked_text: null,
          stages: [],
          classifier_trace: null,
          judge: null,
          training_sample_id: null,
          raw_result: null,
          delivered_result: null,
        })
      }),
    )
    renderWithProviders(<ResourceSimulator />)

    await fillForm(user, '{"path": ".env"}')
    await user.click(screen.getByRole('button', { name: 'Simulate' }))

    expect(await screen.findByText('BLOCKED')).toBeInTheDocument()
    expect(screen.getByText('authorization · resource_scope')).toBeInTheDocument()
    expect(body).toEqual({
      actor: 'marek.nowak',
      kind: 'tool_call',
      tool_call: { server: 'hr-db', tool: 'query', arguments: { path: '.env' } },
    })
    expect(screen.queryByText(/Redacted columns/)).not.toBeInTheDocument()
  })

  it('shows string results verbatim and reads redactions from the reason when evidence is absent', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${CONTROL_LAYER_URL}/api/workbench/trace`, () =>
        HttpResponse.json({
          ...PROJECTION_TRACE_FIXTURE,
          stages: [{ ...projectionStage, violations: [{ ...projectionStage.violations[0], evidence: [] }] }],
          raw_result: 'plain {text} body',
          delivered_result: 'plain body',
        }),
      ),
    )
    renderWithProviders(<ResourceSimulator />)

    await fillForm(user)
    await user.click(screen.getByRole('button', { name: 'Simulate' }))

    expect(await screen.findByText('plain {text} body')).toBeInTheDocument()
    expect(screen.getByText('plain body')).toBeInTheDocument()
    expect(screen.getByText('Redacted columns: salary')).toBeInTheDocument()
    expect(screen.getByText('Rows filtered: 1')).toBeInTheDocument()
  })

  it('rejects invalid argument JSON without calling the backend', async () => {
    const user = userEvent.setup()
    let called = false
    server.use(
      http.post(`${CONTROL_LAYER_URL}/api/workbench/trace`, () => {
        called = true
        return HttpResponse.json({})
      }),
    )
    renderWithProviders(<ResourceSimulator />)

    await fillForm(user, '{not json')
    await user.click(screen.getByRole('button', { name: 'Simulate' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Arguments must be a valid JSON object')
    await waitFor(() => expect(called).toBe(false))
  })
})
