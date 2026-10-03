import { Link, useParams } from 'react-router-dom'
import { useAuditDetail } from '../api/audit'
import { AdminHeader } from '../components/layout/AdminHeader'
import { MetaGrid, type MetaItem } from '../components/audit/MetaGrid'
import { StageTimingBar } from '../components/audit/StageTimingBar'
import { StatusBadge } from '../components/common/StatusBadge'
import { PreBlock } from '../components/common/PreBlock'
import { Spinner } from '../components/common/Spinner'
import { ErrorBanner } from '../components/common/ErrorBanner'
import { errorMessage } from '../lib/errorMessage'
import { formatDecision } from '../lib/formatDecision'
import { roleLabel } from '../lib/roleLabel'
import { downloadJson } from '../lib/downloadJson'

export function CallDetail() {
  const { callId } = useParams<{ callId: string }>()
  const detail = useAuditDetail(callId)

  return (
    <div className="flex min-h-screen flex-col">
      <AdminHeader
        actions={
          detail.data ? (
            <button
              type="button"
              onClick={() => downloadJson(`${detail.data?.call_id}.json`, detail.data)}
              className="min-h-11 rounded-lg border border-[#5A5F66] bg-transparent px-4.5 text-sm font-medium text-white"
            >
              Export JSON
            </button>
          ) : null
        }
      />

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-8 py-7">
        <div className="flex flex-col gap-2.5">
          <Link to="/admin/audit" className="text-sm">
            ← Back to audit log
          </Link>
          {detail.data ? (
            <div className="flex flex-wrap items-center gap-3.5">
              <h1 className="m-0 text-[30px] font-semibold tracking-tight">
                Call #{detail.data.call_id} · {detail.data.target}
              </h1>
              <StatusBadge status={detail.data.decision.status} />
            </div>
          ) : null}
        </div>

        {detail.isLoading ? <Spinner label="Loading call…" /> : null}
        {detail.isError ? <ErrorBanner message={errorMessage(detail.error)} /> : null}

        {detail.data ? <CallDetailBody detail={detail.data} /> : null}
      </div>
    </div>
  )
}

function CallDetailBody({ detail }: { detail: NonNullable<ReturnType<typeof useAuditDetail>['data']> }) {
  const meta: MetaItem[] = [
    { label: 'Time', value: new Date(detail.timestamp).toLocaleString(undefined, { hour12: false }) },
    { label: 'User', value: detail.identity.name },
    { label: 'Role', value: roleLabel(detail.identity.role) },
    { label: 'Location', value: detail.identity.location },
    { label: 'MCP server', value: detail.mcp_server ?? '—' },
    { label: 'Decision', value: formatDecision(detail.decision.status) },
    { label: 'Items masked', value: String(detail.items_masked) },
    { label: 'Proxy latency', value: `${detail.latency.proxy_ms} ms` },
  ]

  return (
    <>
      <MetaGrid items={meta} />

      <section className="flex flex-col gap-3 rounded-[10px] border border-border bg-white px-6 py-5">
        <h2 className="m-0 text-[17px] font-semibold">Per-stage timing</h2>
        <StageTimingBar stages={detail.latency.stages} />
      </section>

      {detail.matched_rule_yaml ? (
        <section className="flex flex-col gap-3 rounded-[10px] border border-border bg-white px-6 py-5">
          <h2 className="m-0 text-[17px] font-semibold">Matched rule</h2>
          <PreBlock>{detail.matched_rule_yaml}</PreBlock>
        </section>
      ) : null}

      <section className="flex flex-col gap-3 rounded-[10px] border border-border bg-white px-6 py-5">
        <h2 className="m-0 text-[17px] font-semibold">Request</h2>
        <PreBlock>{detail.request.summary}</PreBlock>
      </section>

      <section className="flex flex-col gap-3.5 rounded-[10px] border border-border bg-white px-6 py-5">
        <h2 className="m-0 text-[17px] font-semibold">Response</h2>
        <div className="flex flex-wrap gap-4">
          <div className="flex min-w-0 flex-1 basis-[360px] flex-col gap-2">
            <span className="text-[13px] font-semibold" style={{ color: '#A3301A' }}>
              Before masking (admin only)
            </span>
            <PreBlock tone="danger">{detail.response.raw}</PreBlock>
          </div>
          <div className="flex min-w-0 flex-1 basis-[360px] flex-col gap-2">
            <span className="text-[13px] font-semibold" style={{ color: '#17613F' }}>
              Sent to agent
            </span>
            <PreBlock tone="success">{detail.response.delivered}</PreBlock>
          </div>
        </div>
      </section>
    </>
  )
}
