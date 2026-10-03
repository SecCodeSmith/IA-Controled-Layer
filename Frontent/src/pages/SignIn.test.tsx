import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SignIn } from './SignIn'
import { renderWithProviders } from '../test/renderWithProviders'

describe('SignIn', () => {
  it('lists the demo users from the mock SSO directory', async () => {
    renderWithProviders(<SignIn />)

    expect(await screen.findByText('Anna Kowalska')).toBeInTheDocument()
    expect(screen.getByText('Marek Nowak')).toBeInTheDocument()
    expect(screen.getByText('John Smith')).toBeInTheDocument()
    expect(screen.getByText('Ewa Zielinska')).toBeInTheDocument()
    expect(screen.getByText('Developer · Krakow, PL')).toBeInTheDocument()
  })

  it('stores the token and identity and navigates to /chat on selection', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SignIn />, {
      route: '/',
      path: '/',
      extraRoutes: [{ path: '/chat', element: <div>CHAT_PAGE_STUB</div> }],
    })

    const annaRow = await screen.findByText('Anna Kowalska')
    await user.click(annaRow)

    expect(await screen.findByText('CHAT_PAGE_STUB')).toBeInTheDocument()

    const stored = localStorage.getItem('control-layer.session')
    expect(stored).not.toBeNull()
    const parsed = JSON.parse(stored ?? '{}')
    expect(parsed.identity.sub).toBe('anna.kowalska')
    expect(typeof parsed.token).toBe('string')
  })

  it('links to the admin dashboard', async () => {
    renderWithProviders(<SignIn />)
    await waitFor(() => expect(screen.getByText('Open admin dashboard')).toBeInTheDocument())
  })
})
