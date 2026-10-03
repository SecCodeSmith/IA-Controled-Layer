import { useState } from 'react'
import { useAuditList, auditExportUrl } from '../api/audit'
import { AdminHeader } from '../components/layout/AdminHeader'
import { AuditFilters, type AuditFilterValue } from '../components/audit/AuditFilters'
import { AuditTable } from '../components/audit/AuditTable'
import { Spinner } from '../components/common/Spinner'
import { ErrorBanner } from '../components/common/ErrorBanner'
import { errorMessage } from '../lib/errorMessage'

export function AuditLog() {
  const [filter, setFilter] = useState<AuditFilterValue>({ user: '', status: '', kind: '' })
  const audit = useAuditList({
    user: filter.user || undefined,
    status: filter.status || undefined,
    kind: filter.kind || undefined,
  })

  return (
    <div className="flex min-h-screen flex-col">
      <AdminHeader />

      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-5 px-8 py-7">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h1 className="m-0 text-[28px] font-semibold tracking-tight">Audit log</h1>
          <div className="flex gap-2 font-mono text-xs text-muted">
            <a href={auditExportUrl('csv')}>CSV</a>
            <span>·</span>
            <a href={auditExportUrl('jsonl')}>JSONL</a>
            <span>·</span>
            <a href={auditExportUrl('xlsx')}>XLSX</a>
          </div>
        </div>

        <section className="rounded-[10px] border border-border bg-white">
          <div className="border-b border-border px-6 py-5">
            <AuditFilters value={filter} onChange={setFilter} />
          </div>
          {audit.isLoading ? <Spinner label="Loading audit log…" /> : null}
          {audit.isError ? (
            <div className="p-6">
              <ErrorBanner message={errorMessage(audit.error)} />
            </div>
          ) : null}
          {audit.data ? <AuditTable items={audit.data.items} /> : null}
        </section>
      </div>
    </div>
  )
}
