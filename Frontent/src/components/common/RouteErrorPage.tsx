import { Link, useRouteError } from 'react-router-dom'

function describeError(error: unknown): string {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error !== null && 'statusText' in error) {
    return String((error as { statusText: unknown }).statusText)
  }
  return String(error)
}

export function RouteErrorPage() {
  const error = useRouteError()

  return (
    <main className="mx-auto flex w-full max-w-[720px] flex-col gap-4 px-8 py-16">
      <h1 className="m-0 text-[17px] font-semibold">This page failed to render</h1>
      <p role="alert" className="m-0 rounded-[10px] border border-border bg-white px-4 py-3 font-mono text-[13px]">
        {describeError(error)}
      </p>
      <Link to="/admin" className="text-sm font-medium underline">
        Back to the live feed
      </Link>
    </main>
  )
}
