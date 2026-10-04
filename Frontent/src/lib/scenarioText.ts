import type { AttackRun, Scenario, ScenarioStep } from '../types/attack'

function formatValue(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value)
}

function formatArguments(args: Record<string, unknown>): string {
  const pairs = Object.entries(args).map(([key, value]) => `${key}: ${formatValue(value)}`)
  return `{${pairs.join(', ')}}`
}

export function formatStep(step: ScenarioStep): string {
  const parts: string[] = [step.action]
  if (step.server || step.tool) parts.push([step.server, step.tool].filter(Boolean).join('.'))
  if (step.times) parts.push(`×${step.times}`)
  if (step.vary) parts.push(`vary=${step.vary}`)
  if (step.step) parts.push(`step=${step.step}`)
  if (step.claim) parts.push(`claim=${step.claim}`)
  if (step.value !== undefined) parts.push(`value=${formatValue(step.value)}`)
  if (step.model) parts.push(`model=${step.model}`)
  if (step.max_tokens) parts.push(`max_tokens=${step.max_tokens}`)
  if (step.message) parts.push(`"${step.message}"`)
  if (step.arguments) parts.push(formatArguments(step.arguments))
  return parts.join(' ')
}

export function stageRule(stage?: string | null, ruleId?: string | null): string {
  if (stage && ruleId) return `${stage} · ${ruleId}`
  return stage ?? ruleId ?? '–'
}

export function buildReport(run: AttackRun, scenarios: Scenario[]): string {
  const header = `Attack suite run #${run.number} · ${run.model} via ${run.provider} · protection ${run.protection_mode} · agent tier ${run.agent}`
  const lines = scenarios.map((scenario) => {
    const status = scenario.status ?? 'PENDING'
    const note = scenario.explanation ?? scenario.error ?? ''
    return `${status} · ${scenario.name}${note ? ` — ${note}` : ''}`
  })
  return [header, ...lines].join('\n')
}
