type Listener = (event: MessageEvent<string>) => void

export class MockEventSource {
  static instances: MockEventSource[] = []

  url: string
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  private listeners: Record<string, Listener[]> = {}

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, listener: Listener): void {
    this.listeners[type] = [...(this.listeners[type] ?? []), listener]
  }

  removeEventListener(type: string, listener: Listener): void {
    this.listeners[type] = (this.listeners[type] ?? []).filter((candidate) => candidate !== listener)
  }

  close(): void {
    this.closed = true
  }

  emit(type: string, data: unknown): void {
    const event = { data: JSON.stringify(data) } as MessageEvent<string>
    for (const listener of this.listeners[type] ?? []) listener(event)
  }

  static reset(): void {
    MockEventSource.instances = []
  }

  static latest(): MockEventSource | undefined {
    return MockEventSource.instances[MockEventSource.instances.length - 1]
  }
}
