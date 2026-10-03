import { useSecurityReport } from '../api/reports'
import { auditExportUrl } from '../api/audit'
import { alertsExportUrl } from '../api/alerts'
import { AdminHeader } from '../components/layout/AdminHeader'
import { PreBlock } from '../components/common/PreBlock'
import { Spinner } from '../components/common/Spinner'
import { ErrorBanner } from '../components/common/ErrorBanner'
import { errorMessage } from '../lib/errorMessage'

function formatSummaryLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function Reports() {
  const report = useSecurityReport()

  return (
    <div className="flex min-h-screen flex-col">
      <AdminHeader />

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-5 px-8 py-7">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-col gap-1.5">
            <h1 className="m-0 text-[30px] font-semibold tracking-tight">Security report</h1>
            {report.data ? (
              <span className="text-sm text-muted">
                Generated {new Date(report.data.generated_at).toLocaleString(undefined, { hour12: false })} ·
                period {report.data.period}
              </span>
            ) : null}
          </div>
          <div className="flex gap-2 font-mono text-xs text-muted">
            <a href={auditExportUrl('csv')}>Audit CSV</a>
            <span>·</span>
            <a href={auditExportUrl('jsonl')}>Audit JSONL</a>
            <span>·</span>
            <a href={auditExportUrl('xlsx')}>Audit XLSX</a>
            <span>·</span>
            <a href={alertsExportUrl()}>Alerts XLSX</a>
          </div>
        </div>

        {report.isLoading ? <Spinner label="Loading report…" /> : null}
        {report.isError ? <ErrorBanner message={errorMessage(report.error)} /> : null}

        {report.data ? (
          <>
            <div className="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-4">
              {Object.entries(report.data.summary).map(([label, value]) => (
                <div key={label} className="flex flex-col gap-1.5 rounded-[10px] border border-border bg-white px-5 py-4.5">
                  <span className="text-sm text-muted">{formatSummaryLabel(label)}</span>
                  <span className="text-[28px] font-semibold tracking-tight">{String(value)}</span>
                </div>
              ))}
            </div>

            <section className="overflow-hidden rounded-[10px] border border-border bg-white">
              <PreBlock>{report.data.markdown}</PreBlock>
            </section>
          </>
        ) : null}
      </div>
    </div>
  )
}
