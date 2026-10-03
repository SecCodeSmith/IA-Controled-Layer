import type { ProviderInfo, UserRole } from './common'
import type { ProtectionRef } from './protection'

export interface Identity {
  sub: string
  name: string
  role: UserRole
  location: string
  region: string
  agent_id?: string
  session_id?: string
}

export interface DemoUser {
  sub: string
  name: string
  initials: string
  role: UserRole
  location: string
  region: string
  mcp_servers: string[]
}

export interface AuthUsersResponse {
  users: DemoUser[]
}

export interface TokenClaims {
  sub: string
  name: string
  role: UserRole
  location: string
  region: string
  agent_id?: string
  iss?: string
  iat?: number
  exp?: number
}

export interface AuthTokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  claims: TokenClaims
}

export interface ToolDescriptor {
  server: string
  name: string
  qualified_name: string
  description: string
  input_schema: Record<string, unknown>
  tags: string[]
  data_region: string | null
  scope: string
  provisioned?: boolean
}

export interface BudgetUsage {
  tokens_used: number
  tokens_limit: number
  cost_used_usd: number
  cost_limit_usd: number
  resets_at: string
}

export interface RiskProfile {
  score: number
  level: string
}

export interface PolicyRef {
  name: string
  version: number
}

export interface MeResponse {
  identity: Identity
  tools: ToolDescriptor[]
  policy: PolicyRef
  budget: BudgetUsage
  risk: RiskProfile
  provider: ProviderInfo
  protection?: ProtectionRef
}
