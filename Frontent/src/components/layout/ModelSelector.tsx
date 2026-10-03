import { useModels, useSelectModel } from '../../api/models'

function optionValue(provider: string, model: string): string {
  return `${provider}|${model}`
}

export function ModelSelector() {
  const models = useModels()
  const selectModel = useSelectModel()

  if (!models.data) return null

  const { active, available } = models.data
  const activeEntry = available.find(
    (entry) => entry.provider === active.name && entry.model === active.model,
  )
  const notAllowlisted = activeEntry ? !activeEntry.allowed : false

  function handleChange(value: string) {
    const [provider, model] = value.split('|')
    selectModel.mutate({ provider, model })
  }

  return (
    <div className="flex flex-col gap-0.5">
      <label className="flex items-center gap-2 text-xs text-header-muted">
        Model
        <select
          aria-label="Model"
          value={optionValue(active.name, active.model)}
          disabled={selectModel.isPending}
          onChange={(event) => handleChange(event.target.value)}
          className="rounded-md border border-[#5A5F66] bg-header px-2 py-1.5 text-sm text-white"
        >
          {available.map((entry) => (
            <option
              key={optionValue(entry.provider, entry.model)}
              value={optionValue(entry.provider, entry.model)}
            >
              {entry.provider} / {entry.model}
              {entry.size_gb ? ` (${entry.size_gb} GB)` : ''}
              {entry.allowed ? ' · allowed' : ' · not allowlisted'}
            </option>
          ))}
        </select>
      </label>
      {notAllowlisted ? (
        <span className="text-xs" style={{ color: '#F8ECCF' }} role="alert">
          Not allowlisted: prompts will be blocked until the policy allows this model.
        </span>
      ) : null}
    </div>
  )
}
