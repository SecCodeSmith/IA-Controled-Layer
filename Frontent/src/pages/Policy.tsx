import { usePolicy, usePolicyReload } from '../api/policy'
import { AdminHeader } from '../components/layout/AdminHeader'
import { StatusBadge } from '../components/common/StatusBadge'
import { PreBlock } from '../components/common/PreBlock'
import { Spinner } from '../components/common/Spinner'
import { ErrorBanner } from '../components/common/ErrorBanner'
import { RulesByStage } from '../components/policy/RulesByStage'
import { errorMessage } from '../lib/errorMessage'

export function Policy() {
  const policy = usePolicy()
  const reload = usePolicyReload()

  return (
    <div className="flex min-h-screen flex-col">
      <AdminHeader />

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-5 px-8 py-7">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-col gap-1.5">
            <h1 className="m-0 text-[30px] font-semibold tracking-tight">Active policy</h1>
            <span className="text-sm text-muted">
              policy.yaml{policy.data ? ` · v${policy.data.version}` : ''} · read-only, edited in the repo
            </span>
          </div>
          <div className="flex items-center gap-3">
            {policy.data ? <StatusBadge status={policy.data.status} /> : null}
            <button
              type="button"
              onClick={() => void reload.mutateAsync()}
              disabled={reload.isPending}
              className="min-h-10 rounded-lg border border-border bg-white px-4 text-sm font-medium text-ink disabled:opacity-50"
            >
              Reload
            </button>
          </div>
        </div>

        {policy.isLoading ? <Spinner label="Loading policy…" /> : null}
        {policy.isError ? <ErrorBanner message={errorMessage(policy.error)} /> : null}
        {policy.data?.status === 'ERROR' && policy.data.error ? (
          <ErrorBanner message={policy.data.error} />
        ) : null}

        {policy.data ? (
          <>
            <section className="overflow-hidden rounded-[10px] border border-border bg-white">
              <PreBlock>{policy.data.raw_yaml}</PreBlock>
            </section>

            <section className="flex flex-col gap-4 rounded-[10px] border border-border bg-white px-6 py-5">
              <h2 className="m-0 text-[17px] font-semibold">Rules by stage</h2>
              <RulesByStage rulesByStage={policy.data.rules_by_stage} />
            </section>
          </>
        ) : null}
      </div>
    </div>
  )
}
