import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { ResourceMatrix } from './ResourceMatrix'
import { renderWithProviders } from '../../test/renderWithProviders'

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
})
