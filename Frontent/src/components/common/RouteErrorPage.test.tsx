import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { RouteErrorPage } from './RouteErrorPage'

function Exploding(): never {
  throw new TypeError('Cannot read properties of undefined')
}

describe('RouteErrorPage', () => {
  it('shows the error message and a way back when a route throws', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const router = createMemoryRouter(
      [{ path: '/broken', element: <Exploding />, errorElement: <RouteErrorPage /> }],
      { initialEntries: ['/broken'] },
    )

    render(<RouterProvider router={router} />)

    expect(screen.getByRole('alert')).toHaveTextContent('Cannot read properties of undefined')
    expect(screen.getByRole('link', { name: /back to the live feed/i })).toHaveAttribute('href', '/admin')
  })
})
