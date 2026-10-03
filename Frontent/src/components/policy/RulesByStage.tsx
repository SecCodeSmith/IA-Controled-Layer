import { PIPELINE_STAGE_ORDER } from '../../types/common'
import type { RulesByStage as RulesByStageType } from '../../types/policy'

interface RulesByStageProps {
  rulesByStage: RulesByStageType
  onToggle: (ruleId: string, enabled: boolean) => void
  toggling: boolean
}

export function RulesByStage({ rulesByStage, onToggle, toggling }: RulesByStageProps) {
  return (
    <div className="flex flex-col gap-5">
      {PIPELINE_STAGE_ORDER.map((stage) => {
        const rules = rulesByStage[stage] ?? []
        if (rules.length === 0) return null
        return (
          <section key={stage} className="flex flex-col gap-2.5">
            <h3 className="m-0 text-sm font-semibold uppercase tracking-wide text-muted">{stage}</h3>
            <div className="flex flex-col gap-2">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className="flex flex-wrap items-center gap-3 rounded-lg border border-border-soft px-4 py-2.5"
                >
                  <input
                    type="checkbox"
                    role="switch"
                    aria-label={`Toggle ${rule.id}`}
                    checked={rule.enabled !== false}
                    disabled={toggling}
                    onChange={(event) => onToggle(rule.id, event.target.checked)}
                  />
                  <span
                    className="font-mono text-[13px]"
                    style={rule.enabled === false ? { textDecoration: 'line-through', opacity: 0.6 } : undefined}
                  >
                    {rule.id}
                  </span>
                  {rule.overridden ? (
                    <span
                      className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                      style={{ background: '#F8ECCF', color: '#7A4E00' }}
                    >
                      overridden
                    </span>
                  ) : null}
                  <span className="text-xs text-muted">{rule.action}</span>
                  {rule.severity ? <span className="text-xs text-muted">severity: {rule.severity}</span> : null}
                  {rule.owasp && rule.owasp.length > 0 ? (
                    <div className="flex gap-1.5">
                      {rule.owasp.map((tag) => (
                        <span
                          key={tag}
                          className="rounded bg-border-soft px-2 py-0.5 text-[11px] font-medium text-muted"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}
