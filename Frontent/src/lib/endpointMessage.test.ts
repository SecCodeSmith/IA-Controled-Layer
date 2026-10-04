import { describe, expect, it } from 'vitest'
import { ApiError } from '../types/common'
import { endpointMessage } from './endpointMessage'

const hint = 'The control layer does not expose /api/x. Restart it with the current code.'

describe('endpointMessage', () => {
  it('appends the hint to a 404 reason', () => {
    const error = new ApiError({ error: { code: 'not_found', reason: 'Not Found' } }, 404)
    expect(endpointMessage(error, '/api/x')).toBe(`Not Found ${hint}`)
  })

  it('appends the hint to a network failure', () => {
    expect(endpointMessage(new TypeError('Failed to fetch'), '/api/x')).toBe(`Failed to fetch ${hint}`)
  })

  it('leaves other API errors untouched', () => {
    const error = new ApiError({ error: { code: 'boom', reason: 'Sample store unavailable' } }, 500)
    expect(endpointMessage(error, '/api/x')).toBe('Sample store unavailable')
  })
})
