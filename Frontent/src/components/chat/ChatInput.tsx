import { useState, type FormEvent } from 'react'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled: boolean
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  return (
    <form onSubmit={handleSubmit} className="mt-auto flex flex-col gap-2 border-t border-border px-7 py-4.5">
      <label htmlFor="msg" className="text-[13px] text-muted">
        Message your agent
      </label>
      <div className="flex gap-2.5">
        <input
          id="msg"
          type="text"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Ask about code, CI, logs or tickets…"
          className="min-h-11 min-w-0 flex-1 rounded-lg border border-border px-3.5 text-[15px]"
        />
        <button
          type="submit"
          disabled={disabled}
          className="min-h-11 rounded-lg bg-ink px-5.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </form>
  )
}
