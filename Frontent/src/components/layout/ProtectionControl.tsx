import { useProtection, useSetProtection } from '../../api/protection'
import { changedText } from '../../lib/clock'
import { PROTECTION_COLORS, PROTECTION_LABELS } from '../../lib/protectionStyle'
import type { ProtectionMode } from '../../types/protection'

const MODES: ProtectionMode[] = ['enforce', 'monitor', 'off']
const OFF_WARNING =
  'Turn protection OFF? Only identity and audit will run; every call will be allowed unchecked.'

export function ProtectionControl() {
  const protection = useProtection()
  const setProtection = useSetProtection()
  const mode = protection.data?.mode
  const changed = changedText(protection.data?.changed_at, protection.data?.changed_by)

  function handleSelect(next: ProtectionMode) {
    if (next === mode) return
    if (next === 'off' && !window.confirm(OFF_WARNING)) return
    setProtection.mutate(next)
  }

  return (
    <div className="flex items-center gap-2" role="group" aria-label="Protection mode" title={changed ?? undefined}>
      <span className="text-xs text-header-muted">Protection</span>
      <div className="flex overflow-hidden rounded-lg border border-[#5A5F66]">
        {MODES.map((candidate) => (
          <button
            key={candidate}
            type="button"
            aria-pressed={mode === candidate}
            disabled={!protection.data || setProtection.isPending}
            onClick={() => handleSelect(candidate)}
            className={`px-3 py-1.5 text-sm ${mode === candidate ? 'font-semibold' : 'text-header-muted'}`}
            style={
              mode === candidate
                ? {
                    background: PROTECTION_COLORS[candidate].bg,
                    color: PROTECTION_COLORS[candidate].fg,
                  }
                : undefined
            }
          >
            {PROTECTION_LABELS[candidate]}
          </button>
        ))}
      </div>
      {changed ? <span className="text-[11px] text-header-muted">{changed}</span> : null}
    </div>
  )
}
