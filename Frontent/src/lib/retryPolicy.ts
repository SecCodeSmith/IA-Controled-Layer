import { ApiError } from '../types/common'

const MAX_RETRIES = 2
const FIRST_CLIENT_ERROR = 400
const FIRST_SERVER_ERROR = 500

function isClientError(error: unknown): boolean {
  return error instanceof ApiError && error.httpStatus >= FIRST_CLIENT_ERROR && error.httpStatus < FIRST_SERVER_ERROR
}

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  return !isClientError(error) && failureCount < MAX_RETRIES
}
