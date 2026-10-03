export function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="rounded-lg border px-4 py-3 text-sm"
      style={{ background: '#FDF3F0', borderColor: '#FADFD7', color: '#A3301A' }}
      role="alert"
    >
      {message}
    </div>
  )
}
