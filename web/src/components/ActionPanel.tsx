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
