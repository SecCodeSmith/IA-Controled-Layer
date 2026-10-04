import { useState } from 'react'
import { AdminHeader } from '../components/layout/AdminHeader'
import { PromptLab } from '../components/workbench/PromptLab'
import { ResourceMatrix } from '../components/workbench/ResourceMatrix'
import { ResourceSimulator } from '../components/workbench/ResourceSimulator'
import { RetrainPanel } from '../components/workbench/RetrainPanel'
import { StageStrip } from '../components/workbench/StageStrip'
import { TrainingSetPanel } from '../components/workbench/TrainingSetPanel'
import { WorkbenchCard } from '../components/workbench/WorkbenchCard'
import type { TraceResponse } from '../types/workbench'

export function Workbench() {
  const [trace, setTrace] = useState<TraceResponse | null>(null)

  return (
    <div className="flex min-h-screen flex-col">
      <AdminHeader />

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-5 px-8 py-7">
        <div className="flex flex-col gap-1.5">
          <h1 className="m-0 text-[30px] font-semibold tracking-tight">Workbench</h1>
          <span className="text-sm text-muted">
            Real pipeline traces, audited like normal calls{trace ? ` · last call ${trace.call_id}` : ''}
          </span>
        </div>

        <StageStrip stages={trace?.stages ?? null} />

        <WorkbenchCard title="Prompt lab" subtitle="Run a prompt through the seven stages and see why it was decided">
          <PromptLab onTrace={setTrace} />
        </WorkbenchCard>

        <WorkbenchCard
          title="Judge-managed training set"
          subtitle="Judge verdicts become labelled samples; review them, then retrain the tree"
        >
          <TrainingSetPanel />
          <RetrainPanel />
        </WorkbenchCard>

        <WorkbenchCard title="Resource scope" subtitle="Per-role path, row and column scopes on tool calls">
          <ResourceMatrix />
          <ResourceSimulator onTrace={setTrace} />
        </WorkbenchCard>
      </div>
    </div>
  )
}
