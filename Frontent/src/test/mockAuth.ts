import type { TokenClaims } from '../types/identity'

export function encodeMockToken(claims: TokenClaims): string {
  const payload = btoa(JSON.stringify(claims))
  return `mockhdr.${payload}.mocksig`
}

export function decodeMockToken(authorizationHeader: string | null): TokenClaims | null {
  if (!authorizationHeader) return null
  const token = authorizationHeader.replace(/^Bearer\s+/i, '')
  const segments = token.split('.')
  if (segments.length < 2) return null
  try {
    return JSON.parse(atob(segments[1])) as TokenClaims
  } catch {
    return null
  }
}
