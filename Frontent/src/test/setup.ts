import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from './server'
import { resetMockState } from './handlers'

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))

afterEach(() => {
  server.resetHandlers()
  resetMockState()
  localStorage.clear()
  sessionStorage.clear()
})

afterAll(() => server.close())
