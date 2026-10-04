import { useState } from 'react'
import { useSecurityReport } from '../api/reports'
import { auditExportUrl } from '../api/audit'
import { alertsExportUrl } from '../api/alerts'
import { AdminHeader } from '../components/layout/AdminHeader'
import { PreBlock } from '../components/common/PreBlock'
import { MarkdownView } from '../components/common/MarkdownView'
import { Spinner } from '../components/common/Spinner'
import { ErrorBanner } from '../components/common/ErrorBanner'
import { errorMessage } from '../lib/errorMessage'

const BUTTON_CLASS =
  'cursor-pointer rounded-md border border-border bg-white px-3 py-1.5 text-xs font-medium hover:bg-[#F4F5F2]'

function formatSummaryLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function Reports() {
  const report = useSecurityReport()
  const [showRaw, setShowRaw] = useState(false)
  const [copied, setCopied] = useState(false)

  const copyMarkdown = async (markdown: string) => {
    try {
      await navigator.clipboard.writeText(markdown)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  const downloadMarkdown = (markdown: string, period: string) => {
    const url = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `security-report-${period}.md`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

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
              {Object.entries(report.data.summary)
                .filter(([, value]) => typeof value !== 'object' || value === null)
                .map(([label, value]) => (
                <div key={label} className="flex flex-col gap-1.5 rounded-[10px] border border-border bg-white px-5 py-4.5">
                  <span className="text-sm text-muted">{formatSummaryLabel(label)}</span>
                  <span className="text-[28px] font-semibold tracking-tight">{String(value)}</span>
                </div>
              ))}
            </div>

            <section className="overflow-hidden rounded-[10px] border border-border bg-white">
              <div className="flex flex-wrap items-center justify-end gap-2 border-b border-border px-5 py-3">
                <button type="button" className={BUTTON_CLASS} onClick={() => void copyMarkdown(report.data.markdown)}>
                  {copied ? 'Copied' : 'Copy Markdown'}
                </button>
                <button
                  type="button"
                  className={BUTTON_CLASS}
                  onClick={() => downloadMarkdown(report.data.markdown, report.data.period)}
                >
                  Download .md
                </button>
                <button
                  type="button"
                  aria-pressed={showRaw}
                  className={BUTTON_CLASS}
                  onClick={() => setShowRaw((value) => !value)}
                >
                  {showRaw ? 'Show rendered' : 'Show raw'}
                </button>
              </div>
              {showRaw ? (
                <PreBlock>{report.data.markdown}</PreBlock>
              ) : (
                <MarkdownView markdown={report.data.markdown} />
              )}
            </section>
          </>
        ) : null}
      </div>
    </div>
  )
}
