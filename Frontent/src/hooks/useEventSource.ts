import { useEffect, useRef, useState } from 'react'

export type EventSourceHandlers = Record<string, (event: MessageEvent<string>) => void>

export interface UseEventSourceOptions {
  reconnectDelayMs?: number
  terminalEvents?: string[]
}

const DEFAULT_RECONNECT_DELAY_MS = 2000

export function useEventSource(
  url: string | null,
  handlers: EventSourceHandlers,
  options: UseEventSourceOptions = {},
): { connected: boolean } {
  const [connected, setConnected] = useState(false)
  const handlersRef = useRef(handlers)
  const terminalEventsRef = useRef(options.terminalEvents)

  useEffect(() => {
    handlersRef.current = handlers
    terminalEventsRef.current = options.terminalEvents
  }, [handlers, options.terminalEvents])

  useEffect(() => {
    if (!url) {
      return
    }

    let source: EventSource | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined
    let disposed = false

    const dispose = () => {
      disposed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      source?.close()
      setConnected(false)
    }

    const connect = () => {
      if (disposed) return
      source = new EventSource(url)

      source.onopen = () => setConnected(true)
      source.onerror = () => {
        setConnected(false)
        source?.close()
        if (!disposed) {
          reconnectTimer = setTimeout(connect, options.reconnectDelayMs ?? DEFAULT_RECONNECT_DELAY_MS)
        }
      }

      for (const eventName of Object.keys(handlersRef.current)) {
        source.addEventListener(eventName, (event) => {
          handlersRef.current[eventName]?.(event as MessageEvent<string>)
          if (terminalEventsRef.current?.includes(eventName)) dispose()
        })
      }
    }

    connect()

    return dispose
  }, [url, options.reconnectDelayMs])

  return { connected }
}
