import type { SafeActionName, SafeActionResponse } from '../types/api'

type ActionPanelProps = {
  dryRun: boolean
  isPending: boolean
  latestResult: SafeActionResponse | null
  latestError: string | null
  onRunAction: (action: SafeActionName) => void
}

const actions: Array<{ action: SafeActionName; label: string; description: string }> = [
  {
    action: 'smoke-exchange',
    label: 'Smoke Exchange',
    description: '讀取餘額與 lendbook，不建立委託。',
  },
  {
    action: 'sync-history',
    label: 'Sync History',
    description: '同步目前設定幣種的收益紀錄。',
  },
  {
    action: 'sync-open-offers',
    label: 'Sync Open Offers',
    description: '同步交易所未成交委託快照。',
  },
  {
    action: 'cleanup',
    label: 'Cleanup',
    description: '清理過期市場利率紀錄。',
  },
  {
    action: 'run-once',
    label: 'Run Once',
    description: '觸發一次 bot run；Live 模式需要二次確認。',
  },
]

export function ActionPanel({
  dryRun,
  isPending,
  latestResult,
  latestError,
  onRunAction,
}: ActionPanelProps) {
  return (
    <section className="action-panel" id="actions">
      <div className="section-heading compact">
        <div>
          <h2>安全操作</h2>
          <p>
            sync/cleanup 不會建立或取消 live offer；Run Once 會遵守後端 safety guard。
            目前模式：{dryRun ? '模擬模式' : 'Live 模式'}。
          </p>
        </div>
      </div>
      <div className="action-grid">
        {actions.map((item) => (
          <button
            key={item.action}
            type="button"
            className="action-button"
            disabled={isPending}
            onClick={() => onRunAction(item.action)}
          >
            <strong>{item.label}</strong>
            <span>{item.description}</span>
          </button>
        ))}
      </div>
      {latestResult ? <pre className="action-result">{JSON.stringify(latestResult, null, 2)}</pre> : null}
      {latestError ? <div className="action-error">{latestError}</div> : null}
    </section>
  )
}
