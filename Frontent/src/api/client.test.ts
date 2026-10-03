import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../test/server'
import { saveSession } from '../lib/session'
import { ApiError } from '../types/common'
import { adminApi, agentApi, controlLayer, CONTROL_LAYER_URL, AGENT_URL, ADMIN_TOKEN } from './client'

describe('apiRequest', () => {
  it('attaches the Bearer token to control-layer requests', async () => {
    saveSession({
      token: 'test-token-123',
      identity: { sub: 'anna.kowalska', name: 'Anna Kowalska', role: 'developer', location: 'Krakow, PL', region: 'PL' },
    })
    server.use(
      http.get(`${CONTROL_LAYER_URL}/__echo-headers`, ({ request }) =>
        HttpResponse.json({ authorization: request.headers.get('Authorization') }),
      ),
    )

    const result = await controlLayer.get<{ authorization: string | null }>('/__echo-headers')
    expect(result.authorization).toBe('Bearer test-token-123')
  })

  it('attaches the Bearer token to agent requests', async () => {
    saveSession({
      token: 'agent-token-456',
      identity: { sub: 'anna.kowalska', name: 'Anna Kowalska', role: 'developer', location: 'Krakow, PL', region: 'PL' },
    })
    server.use(
      http.post(`${AGENT_URL}/__echo-headers`, ({ request }) =>
        HttpResponse.json({ authorization: request.headers.get('Authorization') }),
      ),
    )

    const result = await agentApi.post<{ authorization: string | null }>('/__echo-headers', {})
    expect(result.authorization).toBe('Bearer agent-token-456')
  })

  it('attaches the X-Admin-Token header to admin requests', async () => {
    server.use(
      http.get(`${CONTROL_LAYER_URL}/__echo-headers`, ({ request }) =>
        HttpResponse.json({ adminToken: request.headers.get('X-Admin-Token') }),
      ),
    )

    const result = await adminApi.get<{ adminToken: string | null }>('/__echo-headers')
    expect(result.adminToken).toBe(ADMIN_TOKEN)
  })

  it('parses the contract error envelope and throws an ApiError', async () => {
    server.use(
      http.get(`${CONTROL_LAYER_URL}/__boom`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'policy_violation',
              status: 'BLOCKED',
              stage: 'authorization',
              rule_id: 'role_provisioning',
              reason: 'HR database is not provisioned for the Developer role',
              owasp: ['ASI03', 'LLM06'],
              call_id: 'c_000139',
            },
          },
          { status: 403 },
        ),
      ),
    )

    let caught: unknown
    try {
      await controlLayer.get('/__boom')
    } catch (error) {
      caught = error
    }

    expect(caught).toBeInstanceOf(ApiError)
    const apiError = caught as ApiError
    expect(apiError.httpStatus).toBe(403)
    expect(apiError.envelope.error.code).toBe('policy_violation')
    expect(apiError.envelope.error.rule_id).toBe('role_provisioning')
    expect(apiError.message).toBe('HR database is not provisioned for the Developer role')
  })
})
