import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { MockEventSource } from '../test/mockEventSource'
import { useEventSource } from './useEventSource'

const RECONNECT_DELAY_MS = 2000

beforeEach(() => {
  vi.useFakeTimers()
  MockEventSource.reset()
  vi.stubGlobal('EventSource', MockEventSource)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function renderStream(terminalEvents?: string[]) {
  const handlers = { progress: vi.fn(), done: vi.fn() }
  const hook = renderHook(() => useEventSource('http://stream', handlers, { terminalEvents }))
  return { ...hook, handlers }
}

describe('useEventSource', () => {
  it('closes without reconnecting after a terminal event', () => {
    const { result, handlers } = renderStream(['done'])
    const source = MockEventSource.latest()
    act(() => source?.onopen?.())
    expect(result.current.connected).toBe(true)

    act(() => source?.emit('done', { ok: true }))
    act(() => source?.onerror?.())
    act(() => {
      vi.advanceTimersByTime(RECONNECT_DELAY_MS * 3)
    })

    expect(handlers.done).toHaveBeenCalledTimes(1)
    expect(source?.closed).toBe(true)
    expect(result.current.connected).toBe(false)
    expect(MockEventSource.instances).toHaveLength(1)
  })

  it('keeps the stream open after a non-terminal event', () => {
    renderStream(['done'])
    const source = MockEventSource.latest()

    act(() => source?.emit('progress', { step: 'a' }))

    expect(source?.closed).toBe(false)
  })

  it('reconnects after an error that follows no terminal event', () => {
    renderStream(['done'])
    const source = MockEventSource.latest()

    act(() => source?.onerror?.())
    act(() => {
      vi.advanceTimersByTime(RECONNECT_DELAY_MS)
    })

    expect(source?.closed).toBe(true)
    expect(MockEventSource.instances).toHaveLength(2)
  })

  it('reconnects after an error when no terminal events are configured', () => {
    renderStream()

    act(() => MockEventSource.latest()?.onerror?.())
    act(() => {
      vi.advanceTimersByTime(RECONNECT_DELAY_MS)
    })

    expect(MockEventSource.instances).toHaveLength(2)
  })

  it('closes the source on unmount', () => {
    const { unmount } = renderStream(['done'])
    const source = MockEventSource.latest()

    unmount()

    expect(source?.closed).toBe(true)
  })
})
