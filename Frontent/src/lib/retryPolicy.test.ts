import { describe, expect, it } from 'vitest'
import { ApiError } from '../types/common'
import { shouldRetryQuery } from './retryPolicy'

const notFound = new ApiError({ error: { code: 'not_found', reason: 'Not Found' } }, 404)
const serverError = new ApiError({ error: { code: 'boom', reason: 'Boom' } }, 500)

describe('shouldRetryQuery', () => {
  it('never retries a client error', () => {
    expect(shouldRetryQuery(0, notFound)).toBe(false)
  })

  it('retries a server error up to the limit', () => {
    expect(shouldRetryQuery(0, serverError)).toBe(true)
    expect(shouldRetryQuery(1, serverError)).toBe(true)
    expect(shouldRetryQuery(2, serverError)).toBe(false)
  })

  it('retries a network failure up to the limit', () => {
    expect(shouldRetryQuery(1, new TypeError('Failed to fetch'))).toBe(true)
    expect(shouldRetryQuery(2, new TypeError('Failed to fetch'))).toBe(false)
  })
})
