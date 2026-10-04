import type { SampleLabel, SamplePatch, TrainingSample } from '../../types/classifier'

const LABEL_NAMES: Record<SampleLabel, string> = { 0: 'benign', 1: 'attack' }

const ACTION_BUTTON_CLASS =
  'min-h-8 rounded-md border border-border bg-white px-2.5 text-xs font-medium text-ink disabled:opacity-50'

interface SamplesTableProps {
  samples: TrainingSample[]
  onPatch: (id: string, patch: SamplePatch) => void
}

function flipped(label: SampleLabel): SampleLabel {
  return label === 1 ? 0 : 1
}

function SampleRow({ sample, onPatch }: { sample: TrainingSample; onPatch: SamplesTableProps['onPatch'] }) {
  return (
    <tr id={`sample-${sample.id}`} className="border-t border-border-soft align-top target:bg-page">
      <td className="max-w-[420px] px-3 py-2.5">
        <div className="line-clamp-2 break-words text-[13px]" title={sample.reason ?? undefined}>
          {sample.text}
        </div>
      </td>
      <td className="whitespace-nowrap px-3 py-2.5 text-[13px]">{LABEL_NAMES[sample.label]}</td>
      <td className="whitespace-nowrap px-3 py-2.5 text-[13px] text-muted">{sample.source}</td>
      <td className="whitespace-nowrap px-3 py-2.5 text-[13px]">{sample.status}</td>
      <td className="whitespace-nowrap px-3 py-2.5 font-mono text-xs text-muted">
        {sample.confidence === null ? '–' : `${Math.round(sample.confidence * 100)}%`}
      </td>
      <td className="whitespace-nowrap px-3 py-2.5">
        <div className="flex gap-1.5">
          <button
            type="button"
            className={ACTION_BUTTON_CLASS}
            disabled={sample.status === 'accepted'}
            onClick={() => onPatch(sample.id, { status: 'accepted' })}
          >
            Accept
          </button>
          <button
            type="button"
            className={ACTION_BUTTON_CLASS}
            disabled={sample.status === 'rejected'}
            onClick={() => onPatch(sample.id, { status: 'rejected' })}
          >
            Reject
          </button>
          <button
            type="button"
            className={ACTION_BUTTON_CLASS}
            onClick={() => onPatch(sample.id, { label: flipped(sample.label) })}
          >
            Flip label
          </button>
        </div>
      </td>
    </tr>
  )
}

export function SamplesTable({ samples, onPatch }: SamplesTableProps) {
  if (samples.length === 0) return <p className="m-0 text-sm text-muted">No samples yet.</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-muted">
            <th className="px-3 py-2 font-medium">Sample</th>
            <th className="px-3 py-2 font-medium">Label</th>
            <th className="px-3 py-2 font-medium">Source</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Judge conf.</th>
            <th className="px-3 py-2 font-medium">Review</th>
          </tr>
        </thead>
        <tbody>
          {samples.map((sample) => (
            <SampleRow key={sample.id} sample={sample} onPatch={onPatch} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
