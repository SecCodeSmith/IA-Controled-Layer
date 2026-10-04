import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import { AdminHeader } from './AdminHeader'
import { renderWithProviders } from '../../test/renderWithProviders'
import { MockEventSource } from '../../test/mockEventSource'

beforeEach(() => {
  MockEventSource.reset()
  vi.stubGlobal('EventSource', MockEventSource)
})

describe('AdminHeader', () => {
  it('links to the Workbench page', () => {
    renderWithProviders(<AdminHeader />, { route: '/admin' })

    const nav = screen.getByRole('navigation', { name: 'Admin' })
    expect(within(nav).getByRole('link', { name: 'Workbench' })).toHaveAttribute('href', '/admin/workbench')
  })
})
