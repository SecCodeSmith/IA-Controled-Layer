export type ProtectionMode = 'enforce' | 'monitor' | 'off'

export interface ProtectionState {
  mode: ProtectionMode
  rule_overrides: Record<string, boolean>
  disabled_rules: string[]
}

export interface ProtectionRef {
  mode: ProtectionMode
}

export interface RuleToggleResponse {
  rule_id: string
  enabled: boolean
  overridden: boolean
}

export interface AvailableModel {
  provider: string
  model: string
  allowed: boolean
  size_gb: number | null
}

export interface ModelsResponse {
  active: { name: string; model: string }
  available: AvailableModel[]
}

export interface ClearLogsResponse {
  ok: boolean
  cleared: string[]
}
