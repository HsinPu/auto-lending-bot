import type { BotLoopStatus, SafeActionName, SafeActionResponse } from '../types/api'
import { formatTimestamp } from '../utils/time'
import { actions } from './actionDefinitions'

type ActionPanelProps = {
  dryRun: boolean
  botLoop: BotLoopStatus
  timeZone: string
  isPending: boolean
  latestResult: SafeActionResponse | null
  latestError: string | null
  onRunAction: (action: SafeActionName) => void
}

export function ActionPanel({
  dryRun,
  botLoop,
  timeZone,
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
            同步與清理不會建立 Live 委託；取消、執行一次、開始持續執行會遵守後端安全檢查。
            目前模式：{dryRun ? '模擬模式' : 'Live 模式'}。
          </p>
        </div>
      </div>
      <div className={`loop-status-card ${botLoop.running ? 'running' : ''}`}>
        <strong>{botLoop.running ? '持續執行中' : '目前未持續執行'}</strong>
        <span>已完成輪數：{botLoop.loops_completed}</span>
        <span>上次執行：{formatTimestamp(botLoop.last_run_at, timeZone)}</span>
        {botLoop.last_error ? <span className="loop-error">錯誤：{botLoop.last_error}</span> : null}
      </div>
      <div className="action-group-list">
        {actionGroups.map((group) => (
          <section className="action-group" key={group.title}>
            <div>
              <h3>{group.title}</h3>
              <p>{group.description}</p>
            </div>
            <div className="action-grid">
              {group.actions.map((actionName) => {
                const item = actions.find((entry) => entry.action === actionName)
                if (!item) {
                  return null
                }

                return (
                  <button
                    key={item.action}
                    type="button"
                    className={`action-button ${group.tone ?? ''}`}
                    disabled={isPending}
                    onClick={() => onRunAction(item.action)}
                  >
                    <strong>{item.label}</strong>
                    <span>{item.description}</span>
                  </button>
                )
              })}
            </div>
          </section>
        ))}
      </div>
      {latestResult ? <pre className="action-result">{JSON.stringify(latestResult, null, 2)}</pre> : null}
      {latestError ? <div className="action-error">{latestError}</div> : null}
    </section>
  )
}

const actionGroups: Array<{
  title: string
  description: string
  actions: SafeActionName[]
  tone?: 'primary' | 'warning'
}> = [
  {
    title: '開始放貸',
    description: '先用執行一次確認策略，再決定是否持續執行。',
    actions: ['run-once', 'start-loop', 'stop-loop'],
    tone: 'primary',
  },
  {
    title: '交易所資料同步',
    description: '只讀取交易所資料並更新本地 SQLite。',
    actions: ['smoke-exchange', 'sync-history', 'sync-open-offers'],
  },
  {
    title: '市場分析',
    description: '收集 lendbook 深度資料，供利率門檻和趨勢判斷使用。',
    actions: ['record-market-analysis', 'start-market-analysis', 'stop-market-analysis', 'cleanup'],
  },
  {
    title: '資金與委託風險操作',
    description: 'Live 模式會碰到真實資金或真實委託，請確認安全保險絲。',
    actions: ['transfer-preview', 'transfer-funds', 'cancel-open-offers'],
    tone: 'warning',
  },
]
