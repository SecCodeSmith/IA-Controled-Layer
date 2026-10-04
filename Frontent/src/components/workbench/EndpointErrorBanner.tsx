import { endpointMessage } from '../../lib/endpointMessage'
import { ErrorBanner } from '../common/ErrorBanner'

export function EndpointErrorBanner({ error, endpoint }: { error: unknown; endpoint: string }) {
  return <ErrorBanner message={endpointMessage(error, endpoint)} />
}
