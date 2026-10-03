import { ApiError } from '../types/common'

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.envelope.error.reason
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Something went wrong'
}
