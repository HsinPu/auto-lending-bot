import type { StatusResponse } from '../types/api'

type TopStatusBarProps = {
  status: StatusResponse | null
  isFetching: boolean
  lastRefreshed: Date | null
  onRefresh: () => void
}

export function TopStatusBar({ status, isFetching, lastRefreshed, onRefresh }: TopStatusBarProps) {
  const latestRun = status?.latest_run

  return (
    <header className="top-status-bar">
      <div className="brand-block">
        <div className="brand-mark">AL</div>
        <div>
          <strong>{status?.label ?? 'Auto Lending Bot'}</strong>
          <span>{lastRefreshed ? `更新：${lastRefreshed.toLocaleTimeString()}` : '尚未更新'}</span>
        </div>
      </div>

      <div className="status-strip" aria-label="執行狀態">
        <StatusPill label="交易所" value={status?.exchange ?? '-'} />
        <StatusPill
          label="模式"
          value={status?.dry_run === false ? 'Live 模式' : '模擬模式'}
          tone={status?.dry_run === false ? 'danger' : 'safe'}
        />
        <StatusPill label="最新執行" value={latestRun ? `#${latestRun.id} ${statusLabel(latestRun.status)}` : '無'} />
      </div>

      <button type="button" className="refresh-button compact" onClick={onRefresh}>
        {isFetching ? '更新中...' : '重新整理'}
      </button>
    </header>
  )
}

const statusLabels: Record<string, string> = {
  completed: '完成',
  failed: '失敗',
  running: '執行中',
}

function statusLabel(status: string): string {
  return statusLabels[status] ?? status
}

function StatusPill({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: 'safe' | 'danger'
}) {
  return (
    <span className={`top-pill ${tone ?? ''}`}>
      <small>{label}</small>
      {value}
    </span>
  )
}
