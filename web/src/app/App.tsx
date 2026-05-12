import { useQuery } from '@tanstack/react-query'

import { getStatus } from '../api/client'
import { StatusCard } from '../components/StatusCard'

function App() {
  const { data, error, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['status'],
    queryFn: getStatus,
  })

  return (
    <main className="shell">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Auto Lending Bot</p>
          <h1>放貸監控前端骨架</h1>
          <p className="lede">第一版先連接 read-only API，後續再擴充完整儀表板與安全操作。</p>
        </div>
        <button type="button" className="refresh-button" onClick={() => void refetch()}>
          {isFetching ? '更新中...' : '重新整理'}
        </button>
      </section>

      {isLoading ? <StatusSkeleton /> : null}
      {error ? <ErrorState message={(error as Error).message} /> : null}
      {data ? (
        <section className="status-grid" aria-label="Bot status summary">
          <StatusCard label="交易所" value={data.exchange} />
          <StatusCard
            label="執行模式"
            value={data.dry_run ? '模擬模式' : 'Live 模式'}
            tone={data.dry_run ? 'safe' : 'danger'}
          />
          <StatusCard label="Bot runs" value={data.counts.bot_runs} />
          <StatusCard label="貸出委託" value={data.counts.loan_offers} />
          <StatusCard label="目前放貸中" value={data.counts.active_loans} />
          <StatusCard label="收益紀錄" value={data.counts.lending_history} />
        </section>
      ) : null}
    </main>
  )
}

function StatusSkeleton() {
  return <section className="status-skeleton">讀取 API 狀態中...</section>
}

function ErrorState({ message }: { message: string }) {
  return (
    <section className="error-state">
      <strong>無法讀取 API</strong>
      <span>{message}</span>
    </section>
  )
}

export default App
