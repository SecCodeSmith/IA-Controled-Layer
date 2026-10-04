import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Reports } from './Reports'
import { renderWithProviders } from '../test/renderWithProviders'
import { SECURITY_REPORT_FIXTURE } from '../test/fixtures'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Reports', () => {
  it('renders the markdown as a heading, list items and a table', async () => {
    renderWithProviders(<Reports />, { route: '/admin/reports' })

    expect(await screen.findByRole('heading', { level: 2, name: 'Top rules' })).toBeInTheDocument()
    // page title plus the report's own H1
    expect(screen.getAllByRole('heading', { level: 1, name: 'Security report' })).toHaveLength(2)
    expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(4)
    expect(screen.getByText('LLM01 Prompt Injection: covered')).toBeInTheDocument()

    const table = screen.getByRole('table')
    expect(within(table).getByRole('columnheader', { name: 'Rule' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: 'Hits' })).toBeInTheDocument()
    expect(within(table).getByRole('cell', { name: 'pii_masking' })).toBeInTheDocument()
    expect(within(table).getByRole('cell', { name: '11' })).toBeInTheDocument()
    expect(within(table).getByRole('cell', { name: 'role_provisioning' })).toBeInTheDocument()
    expect(document.querySelector('pre')).toBeNull()
  })

  it('copies the markdown to the clipboard', async () => {
    const user = userEvent.setup()
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined)
    renderWithProviders(<Reports />, { route: '/admin/reports' })

    await user.click(await screen.findByRole('button', { name: 'Copy Markdown' }))

    expect(writeText).toHaveBeenCalledWith(SECURITY_REPORT_FIXTURE.markdown)
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeInTheDocument()
  })

  it('shows the raw markdown in a pre block when toggled', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Reports />, { route: '/admin/reports' })

    await user.click(await screen.findByRole('button', { name: 'Show raw' }))

    const pre = document.querySelector('pre')
    expect(pre).not.toBeNull()
    expect(pre?.textContent).toBe(SECURITY_REPORT_FIXTURE.markdown)
    expect(screen.queryByRole('table')).toBeNull()
  })
})
