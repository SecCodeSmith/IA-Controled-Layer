import type { JudgeTrace } from '../../types/workbench'
import { AuditLink } from './AuditLink'

interface JudgeCardProps {
  judge: JudgeTrace
  sampleId: string | null
  callId: string
}

export function JudgeCard({ judge, sampleId, callId }: JudgeCardProps) {
  return (
    <article className="flex flex-col gap-2 rounded-lg border border-border-soft px-4 py-3.5">
      <h3 className="m-0 text-[15px] font-semibold">LLM judge</h3>
      <div className="flex items-center gap-3">
        <span className="rounded-full bg-border-soft px-2.5 py-0.5 text-xs font-semibold">{judge.verdict}</span>
        <span className="font-mono text-[13px]">confidence {Math.round(judge.confidence * 100)}%</span>
      </div>
      {judge.reason ? <p className="m-0 text-[13px] text-muted">{judge.reason}</p> : null}
      <div className="flex flex-wrap gap-4 text-[13px]">
        {sampleId ? (
          <a href={`#sample-${sampleId}`} className="text-accent underline">
            Sample {sampleId}
          </a>
        ) : (
          <span className="text-muted">No training sample recorded</span>
        )}
        <AuditLink callId={callId} />
      </div>
    </article>
  )
}
