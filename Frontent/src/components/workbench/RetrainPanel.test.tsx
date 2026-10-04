import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { RetrainPanel } from './RetrainPanel'
import { renderWithProviders } from '../../test/renderWithProviders'
import { MockEventSource } from '../../test/mockEventSource'
import { server } from '../../test/server'
import { CONTROL_LAYER_URL } from '../../api/client'
import { RETRAIN_RESULT_FIXTURE } from '../../test/workbenchFixtures'

beforeEach(() => {
  MockEventSource.reset()
  vi.stubGlobal('EventSource', MockEventSource)
})

describe('RetrainPanel', () => {
  it('posts the retrain request, streams progress and shows the result', async () => {
    const user = userEvent.setup()
    let body: unknown
    server.use(
      http.post(`${CONTROL_LAYER_URL}/api/classifier/retrain`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({
          job_id: 'rj_001',
          status: 'running',
          started_at: '2026-10-04T09:29:00Z',
          result: null,
          error: null,
        })
      }),
    )
    renderWithProviders(<RetrainPanel />)

    await user.click(screen.getByLabelText('Include pending samples'))
    await user.click(screen.getByRole('button', { name: 'Retrain tree' }))

    await waitFor(() => expect(MockEventSource.latest()).toBeDefined())
    expect(body).toEqual({ include_pending: true })
    expect(MockEventSource.latest()?.url).toContain('/api/classifier/retrain/rj_001/stream')
    expect(MockEventSource.latest()?.url).toContain('admin_token=')

    const source = MockEventSource.latest()
    act(() => {
      source?.emit('retrain_progress', { step: 'loading base dataset' })
      source?.emit('retrain_progress', { step: 'fitting tree' })
    })
    expect(await screen.findByText('loading base dataset')).toBeInTheDocument()
    expect(screen.getByText('fitting tree')).toBeInTheDocument()

    act(() => {
      source?.emit('retrain_complete', RETRAIN_RESULT_FIXTURE)
    })

    expect(await screen.findByText('0.912')).toBeInTheDocument()
    expect(screen.getByText('swapped')).toBeInTheDocument()
    expect(screen.getByText('gate passed')).toBeInTheDocument()
    expect(screen.getByText('v4')).toBeInTheDocument()
  })

  it('shows the failure reported by the stream', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RetrainPanel />)

    await user.click(screen.getByRole('button', { name: 'Retrain tree' }))
    await waitFor(() => expect(MockEventSource.latest()).toBeDefined())

    act(() => {
      MockEventSource.latest()?.emit('retrain_failed', { error: 'training crashed' })
    })

    expect(await screen.findByText('training crashed')).toBeInTheDocument()
  })

  it('shows an error banner when a retrain is already running', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${CONTROL_LAYER_URL}/api/classifier/retrain`, () =>
        HttpResponse.json(
          { error: { code: 'retrain_in_progress', reason: 'A retrain is already running' } },
          { status: 409 },
        ),
      ),
    )
    renderWithProviders(<RetrainPanel />)

    await user.click(screen.getByRole('button', { name: 'Retrain tree' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('A retrain is already running')
    expect(MockEventSource.latest()).toBeUndefined()
  })

  it('disables the retrain button while the classifier status is unavailable', async () => {
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/classifier`, () =>
        HttpResponse.json({ error: { code: 'not_found', reason: 'Not Found' } }, { status: 404 }),
      ),
    )
    renderWithProviders(<RetrainPanel />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Retrain tree' })).toBeDisabled())
  })
})
