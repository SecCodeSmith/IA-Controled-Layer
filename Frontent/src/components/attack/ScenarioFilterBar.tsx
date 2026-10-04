import type { ScenarioFilter } from '../../lib/scenarioFilter'

const FILTERS: Array<{ value: ScenarioFilter; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'failed', label: 'Failed' },
  { value: 'not_attempted', label: 'Not attempted' },
  { value: 'ok', label: 'Passed + Stopped' },
]

interface ScenarioFilterBarProps {
  filter: ScenarioFilter
  query: string
  onFilter: (filter: ScenarioFilter) => void
  onQuery: (query: string) => void
}

export function ScenarioFilterBar({ filter, query, onFilter, onQuery }: ScenarioFilterBarProps) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Scenario filter">
        {FILTERS.map((item) => (
          <button
            key={item.value}
            type="button"
            aria-pressed={filter === item.value}
            onClick={() => onFilter(item.value)}
            className={`rounded-full border px-2.5 py-1 text-xs ${
              filter === item.value
                ? 'border-accent bg-accent-soft font-semibold text-accent'
                : 'border-border text-muted'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
      <input
        type="search"
        aria-label="Filter scenarios by name"
        placeholder="Filter by name…"
        value={query}
        onChange={(event) => onQuery(event.target.value)}
        className="min-h-9 rounded-md border border-border px-2.5 text-sm"
      />
    </div>
  )
}
