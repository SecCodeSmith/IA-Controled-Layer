import { useMemo, useState } from 'react'
import { useFeed } from '../api/feed'
import { useStats } from '../api/stats'
import { useResetDemo } from '../api/demo'
import { useFeedStream } from '../hooks/useFeedStream'
import { AdminHeader } from '../components/layout/AdminHeader'
import { KpiCards } from '../components/feed/KpiCards'
import { FeedFilters, ALL_ROLES, ALL_STATUSES, ALL_USERS, type FeedFilterValue } from '../components/feed/FeedFilters'
import { FeedTable } from '../components/feed/FeedTable'
import { AttackSuitePanel } from '../components/attack/AttackSuitePanel'
import { Spinner } from '../components/common/Spinner'
import { roleLabel } from '../lib/roleLabel'
import type { FeedRow } from '../types/feed'

function matchesFilter(row: FeedRow, filter: FeedFilterValue): boolean {
  if (filter.user !== ALL_USERS && row.user.name !== filter.user) return false
  if (filter.role !== ALL_ROLES && roleLabel(row.user.role) !== filter.role) return false
  if (filter.status !== ALL_STATUSES && row.status.toLowerCase() !== filter.status.toLowerCase()) return false
  return true
}

export function LiveFeed() {
  const feed = useFeed()
  const stats = useStats()
  const resetDemo = useResetDemo()
  useFeedStream(true)

  const [filter, setFilter] = useState<FeedFilterValue>({
    user: ALL_USERS,
    role: ALL_ROLES,
    status: ALL_STATUSES,
  })

  const rows = useMemo(
    () => [...(feed.data?.items ?? [])].sort((a, b) => b.time.localeCompare(a.time)),
    [feed.data],
  )
  const userOptions = useMemo(() => Array.from(new Set(rows.map((row) => row.user.name))), [rows])
  const roleOptions = useMemo(
    () => Array.from(new Set(rows.map((row) => roleLabel(row.user.role)))),
    [rows],
  )
  const filteredRows = useMemo(() => rows.filter((row) => matchesFilter(row, filter)), [rows, filter])

  return (
    <div className="flex min-h-screen flex-col">
      <AdminHeader
        actions={
          <button
            type="button"
            onClick={() => void resetDemo.mutateAsync()}
            disabled={resetDemo.isPending}
            className="flex min-h-11 items-center gap-2 rounded-lg border border-[#5A5F66] bg-transparent px-4.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Reset demo
          </button>
        }
      />

      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-6 px-8 py-7">
        <KpiCards
          totalCalls={stats.data?.total_calls ?? 0}
          allowed={stats.data?.allowed ?? 0}
          blocked={stats.data?.blocked ?? 0}
          masked={stats.data?.masked ?? 0}
          escalated={stats.data?.escalated ?? 0}
        />

        <div className="flex flex-wrap items-start gap-6">
          <section className="min-w-0 flex-[999_1_640px] rounded-[10px] border border-border bg-white">
            <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border px-6 py-5">
              <div className="flex items-center gap-2.5">
                <h2 className="m-0 text-lg font-semibold">Live feed</h2>
                <span className="flex items-center gap-1.5 text-[13px]" style={{ color: '#17613F' }}>
                  <span className="h-2 w-2 rounded-full" style={{ background: '#17613F' }} />
                  Live
                </span>
              </div>
              <FeedFilters userOptions={userOptions} roleOptions={roleOptions} value={filter} onChange={setFilter} />
            </div>
            {feed.isLoading ? <Spinner label="Loading feed…" /> : <FeedTable rows={filteredRows} />}
          </section>

          <AttackSuitePanel />
        </div>
      </div>
    </div>
  )
}
