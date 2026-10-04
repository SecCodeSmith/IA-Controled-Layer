import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { ResourceMatrix } from './ResourceMatrix'
import { renderWithProviders } from '../../test/renderWithProviders'
import { server } from '../../test/server'
import { CONTROL_LAYER_URL } from '../../api/client'

describe('ResourceMatrix', () => {
  it('renders resources as rows and roles as columns with the wildcard labelled default', async () => {
    renderWithProviders(<ResourceMatrix />)

    expect(await screen.findByText('github_repo_files')).toBeInTheDocument()
    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent)
    expect(headers).toEqual(['Resource', 'Developer', 'HR Specialist', 'default'])

    const files = screen.getByText('github_repo_files').closest('tr') as HTMLElement
    expect(within(files).getByText('github.read_file')).toBeInTheDocument()
    expect(within(files).getByText(/allow src\/\*\*, docs\/\*\*, README\.md/)).toBeInTheDocument()
    expect(within(files).getByText(/deny \*\*\/\.env, secrets\/\*\*/)).toBeInTheDocument()
    expect(within(files).getAllByText('no grant')).toHaveLength(2)

    const rows = screen.getByText('hr_directory_rows').closest('tr') as HTMLElement
    expect(within(rows).getByText('columns deny salary')).toBeInTheDocument()
    expect(within(rows).getByText('rows region = $identity.region')).toBeInTheDocument()
    expect(within(rows).getByText('columns allow id, name')).toBeInTheDocument()
    expect(within(rows).getByText('rows region in PL, DE')).toBeInTheDocument()
  })

  it.each([
    ['a 404 response', () => HttpResponse.json({ error: { code: 'not_found', reason: 'Not Found' } }, { status: 404 })],
    ['a network error', () => HttpResponse.error()],
  ])('shows the banner with the hint instead of loading on %s', async (_name, failure) => {
    server.use(http.get(`${CONTROL_LAYER_URL}/api/workbench/resources`, failure))
    renderWithProviders(<ResourceMatrix />)

    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent(
      'The control layer does not expose /api/workbench/resources. Restart it with the current code.',
    )
    expect(screen.queryByText(/Loading/)).not.toBeInTheDocument()
  })

  it('names the reason of a 404 in the banner', async () => {
    server.use(
      http.get(`${CONTROL_LAYER_URL}/api/workbench/resources`, () =>
        HttpResponse.json({ error: { code: 'not_found', reason: 'Not Found' } }, { status: 404 }),
      ),
    )
    renderWithProviders(<ResourceMatrix />)

    expect(await screen.findByRole('alert')).toHaveTextContent(/^Not Found/)
  })
})
