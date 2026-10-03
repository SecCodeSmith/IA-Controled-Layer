import type { Identity } from '../types/identity'

export interface StoredSession {
  token: string
  identity: Identity
}

const SESSION_KEY = 'control-layer.session'
const TAB_SESSION_KEY = 'control-layer.tab-session-id'

export function loadSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    return JSON.parse(raw) as StoredSession
  } catch {
    return null
  }
}

export function saveSession(session: StoredSession): void {
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session))
  } catch {
    // localStorage unavailable (private mode, quota) - session stays in-memory for this request only
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(SESSION_KEY)
  } catch {
    // ignore
  }
}

function createId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `s-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function getOrCreateTabSessionId(): string {
  try {
    const existing = sessionStorage.getItem(TAB_SESSION_KEY)
    if (existing) return existing
    const created = createId()
    sessionStorage.setItem(TAB_SESSION_KEY, created)
    return created
  } catch {
    return createId()
  }
}
