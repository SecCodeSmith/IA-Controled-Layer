import { beforeEach, describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { TrainingSetPanel } from './TrainingSetPanel'
import { renderWithProviders } from '../../test/renderWithProviders'
import { server } from '../../test/server'
import { CONTROL_LAYER_URL } from '../../api/client'
import { SAMPLES_FIXTURE } from '../../test/workbenchFixtures'

function capturePatches(): unknown[] {
  const bodies: unknown[] = []
  server.use(
    http.patch(`${CONTROL_LAYER_URL}/api/classifier/samples/:sampleId`, async ({ params, request }) => {
      const body = (await request.json()) as Record<string, unknown>
      bodies.push({ id: params.sampleId, ...body })
      return HttpResponse.json({ ...SAMPLES_FIXTURE[0], ...body })
    }),
  )
  return bodies
}

async function sampleRow(id: string): Promise<HTMLElement> {
  const row = (await screen.findByText(new RegExp(id === 's_001' ? 'Ignore all previous' : 'Delete the stale'))).closest('tr')
  if (!row) throw new Error('row not found')
  return row
}

describe('TrainingSetPanel', () => {
  it('shows the classifier status row and the samples', async () => {
    renderWithProviders(<TrainingSetPanel />)

    expect(await screen.findByText('tree')).toBeInTheDocument()
    expect(screen.getByText('0.885')).toBeInTheDocument()
    expect(screen.getByText('v3')).toBeInTheDocument()
    expect(screen.getByText('2 pending')).toBeInTheDocument()
    expect(screen.getByText('5 accepted')).toBeInTheDocument()
    expect(screen.getByText('1 rejected')).toBeInTheDocument()
    const row = (await screen.findByText(/Summarise the sprint backlog/)).closest('tr') as HTMLElement
    expect(within(row).getByText('–')).toBeInTheDocument()
  })

  it('sends accept, reject and flip as PATCH bodies', async () => {
    const user = userEvent.setup()
    const bodies = capturePatches()
    renderWithProviders(<TrainingSetPanel />)

    const first = await sampleRow('s_001')
    await user.click(within(first).getByRole('button', { name: 'Accept' }))
    await waitFor(() => expect(bodies).toHaveLength(1))

    await user.click(within(first).getByRole('button', { name: 'Reject' }))
    await waitFor(() => expect(bodies).toHaveLength(2))

    await user.click(within(first).getByRole('button', { name: 'Flip label' }))
    await waitFor(() => expect(bodies).toHaveLength(3))

    const second = await sampleRow('s_002')
    await user.click(within(second).getByRole('button', { name: 'Flip label' }))
    await waitFor(() => expect(bodies).toHaveLength(4))

    expect(bodies).toEqual([
      { id: 's_001', status: 'accepted' },
      { id: 's_001', status: 'rejected' },
      { id: 's_001', label: 0 },
      { id: 's_002', label: 1 },
    ])
  })

  it('filters the samples by status', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TrainingSetPanel />)

    await screen.findByText(/Summarise the sprint backlog/)
    await user.selectOptions(screen.getByLabelText('Status filter'), 'accepted')

    await waitFor(() =>
      expect(screen.queryByText(/Ignore all previous/)).not.toBeInTheDocument(),
    )
    expect(screen.getByText(/Summarise the sprint backlog/)).toBeInTheDocument()
  })

  it('curates with the judge and shows the summary', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TrainingSetPanel />)

    await user.click(await screen.findByRole('button', { name: 'Curate with judge' }))

    expect(
      await screen.findByText('Judge reviewed 5 · accepted 3 · rejected 1 · relabelled 1 · refused 0'),
    ).toBeInTheDocument()
  })

  it('shows the curator error reported in the summary', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${CONTROL_LAYER_URL}/api/classifier/samples/curate`, () =>
        HttpResponse.json({ reviewed: 0, accepted: 0, rejected: 0, relabelled: 0, refused: 0, error: 'curator returned malformed JSON' }),
      ),
    )
    renderWithProviders(<TrainingSetPanel />)

    await user.click(await screen.findByRole('button', { name: 'Curate with judge' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('curator returned malformed JSON')
  })

  it('shows an error banner when the samples cannot be loaded', async () => {
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/classifier/samples`, () =>
        HttpResponse.json({ error: { code: 'boom', reason: 'Sample store unavailable' } }, { status: 500 }),
      ),
    )
    renderWithProviders(<TrainingSetPanel />)

    expect(await screen.findByText('Sample store unavailable')).toBeInTheDocument()
  })

  describe.each([
    ['a 404 response', () => HttpResponse.json({ error: { code: 'not_found', reason: 'Not Found' } }, { status: 404 })],
    ['a network error', () => HttpResponse.error()],
  ])('when the classifier endpoints fail with %s', (_name, failure) => {
    beforeEach(() => {
      server.use(
        http.get(`${CONTROL_LAYER_URL}/api/classifier`, failure),
        http.get(`${CONTROL_LAYER_URL}/api/classifier/samples`, failure),
      )
    })

    it('shows one banner with the hint instead of loading forever', async () => {
      renderWithProviders(<TrainingSetPanel />)

      const banner = await screen.findByRole('alert')
      expect(banner).toHaveTextContent(
        'The control layer does not expose /api/classifier. Restart it with the current code.',
      )
      expect(screen.getAllByRole('alert')).toHaveLength(1)
      expect(screen.queryByText('Loading samples…')).not.toBeInTheDocument()
    })

    it('disables curation', async () => {
      renderWithProviders(<TrainingSetPanel />)

      await screen.findByRole('alert')
      expect(screen.getByRole('button', { name: 'Curate with judge' })).toBeDisabled()
    })
  })

  it('names the reason of a 404 in the banner', async () => {
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/classifier`, () =>
        HttpResponse.json({ error: { code: 'not_found', reason: 'Not Found' } }, { status: 404 }),
      ),
    )
    renderWithProviders(<TrainingSetPanel />)

    expect(await screen.findByRole('alert')).toHaveTextContent(/^Not Found/)
  })

  it('shows the samples error and no endless loading when only the samples request fails', async () => {
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/classifier/samples`, () =>
        HttpResponse.json({ error: { code: 'not_found', reason: 'Not Found' } }, { status: 404 }),
      ),
    )
    renderWithProviders(<TrainingSetPanel />)

    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('Not Found')
    expect(banner).toHaveTextContent(
      'The control layer does not expose /api/classifier/samples. Restart it with the current code.',
    )
    expect(screen.queryByText('Loading samples…')).not.toBeInTheDocument()
    expect(await screen.findByText('tree')).toBeInTheDocument()
  })

  it('recovers on its own once the backend serves the endpoints again', async () => {
    let healthy = false
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/classifier/samples`, () =>
        healthy
          ? HttpResponse.json({ items: SAMPLES_FIXTURE })
          : HttpResponse.json({ error: { code: 'not_found', reason: 'Not Found' } }, { status: 404 }),
      ),
    )
    renderWithProviders(<TrainingSetPanel />)

    await screen.findByRole('alert')
    healthy = true

    expect(await screen.findByText(/Summarise the sprint backlog/, undefined, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  }, 10000)
})
