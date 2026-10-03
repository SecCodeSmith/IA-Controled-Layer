import { ApiError, type ErrorEnvelope } from '../types/common'
import { loadSession } from '../lib/session'

export const CONTROL_LAYER_URL: string =
  import.meta.env.VITE_CONTROL_LAYER_URL ?? 'http://localhost:8080'
export const AGENT_URL: string = import.meta.env.VITE_AGENT_URL ?? 'http://localhost:8090'
export const ADMIN_TOKEN: string = import.meta.env.VITE_ADMIN_TOKEN ?? 'admin-dev-token'

type ApiKind = 'control' | 'agent' | 'admin' | 'public'

interface RequestOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
  sessionId?: string
}

function baseUrlFor(kind: ApiKind): string {
  return kind === 'agent' ? AGENT_URL : CONTROL_LAYER_URL
}

function headersFor(kind: ApiKind, hasBody: boolean, sessionId?: string): Record<string, string> {
  const headers: Record<string, string> = {}
  if (hasBody) headers['Content-Type'] = 'application/json'
  if (kind === 'control' || kind === 'agent') {
    const session = loadSession()
    if (session?.token) headers.Authorization = `Bearer ${session.token}`
    if (sessionId) headers['X-Session-Id'] = sessionId
  }
  if (kind === 'admin') {
    headers['X-Admin-Token'] = ADMIN_TOKEN
  }
  return headers
}

function isErrorEnvelope(data: unknown): data is ErrorEnvelope {
  return (
    typeof data === 'object' &&
    data !== null &&
    'error' in data &&
    typeof (data as { error?: unknown }).error === 'object' &&
    (data as { error?: unknown }).error !== null
  )
}

function fallbackEnvelope(status: number): ErrorEnvelope {
  return { error: { code: 'unknown_error', reason: `Request failed with status ${status}` } }
}

export async function apiRequest<T>(
  kind: ApiKind,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const url = `${baseUrlFor(kind)}${path}`
  const hasBody = options.body !== undefined
  const response = await fetch(url, {
    method: options.method ?? (hasBody ? 'POST' : 'GET'),
    headers: headersFor(kind, hasBody, options.sessionId),
    body: hasBody ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  const data: unknown = text ? JSON.parse(text) : undefined

  if (!response.ok) {
    const envelope = isErrorEnvelope(data) ? data : fallbackEnvelope(response.status)
    throw new ApiError(envelope, response.status)
  }

  return data as T
}

export const controlLayer = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>('control', path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>('control', path, { ...options, method: 'POST', body: body ?? {} }),
}

export const agentApi = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>('agent', path, { ...options, method: 'GET' }),
  post: <T>(path: string, body: unknown, options?: RequestOptions) =>
    apiRequest<T>('agent', path, { ...options, method: 'POST', body }),
}

export const adminApi = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>('admin', path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>('admin', path, { ...options, method: 'POST', body: body ?? {} }),
  put: <T>(path: string, body: unknown, options?: RequestOptions) =>
    apiRequest<T>('admin', path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body: unknown, options?: RequestOptions) =>
    apiRequest<T>('admin', path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>('admin', path, { ...options, method: 'DELETE' }),
}

export const publicApi = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>('public', path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>('public', path, { ...options, method: 'POST', body: body ?? {} }),
}

export function adminStreamUrl(path: string): string {
  const separator = path.includes('?') ? '&' : '?'
  return `${CONTROL_LAYER_URL}${path}${separator}admin_token=${encodeURIComponent(ADMIN_TOKEN)}`
}

export function adminExportUrl(path: string): string {
  const separator = path.includes('?') ? '&' : '?'
  return `${CONTROL_LAYER_URL}${path}${separator}admin_token=${encodeURIComponent(ADMIN_TOKEN)}`
}
