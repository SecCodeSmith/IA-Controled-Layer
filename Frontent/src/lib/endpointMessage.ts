import { ApiError } from '../types/common'
import { errorMessage } from './errorMessage'

const NOT_FOUND = 404

function isEndpointMissing(error: unknown): boolean {
  return !(error instanceof ApiError) || error.httpStatus === NOT_FOUND
}

function endpointHint(endpoint: string): string {
  return `The control layer does not expose ${endpoint}. Restart it with the current code.`
}

export function endpointMessage(error: unknown, endpoint: string): string {
  const reason = errorMessage(error)
  return isEndpointMissing(error) ? `${reason} ${endpointHint(endpoint)}` : reason
}
