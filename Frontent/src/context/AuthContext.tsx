import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { clearSession, loadSession, saveSession, type StoredSession } from '../lib/session'
import type { Identity } from '../types/identity'

interface AuthContextValue {
  identity: Identity | null
  token: string | null
  signIn: (session: StoredSession) => void
  signOut: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(() => loadSession())

  const signIn = useCallback((next: StoredSession) => {
    saveSession(next)
    setSession(next)
  }, [])

  const signOut = useCallback(() => {
    clearSession()
    setSession(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      identity: session?.identity ?? null,
      token: session?.token ?? null,
      signIn,
      signOut,
    }),
    [session, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components -- hook lives beside its provider by design
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
