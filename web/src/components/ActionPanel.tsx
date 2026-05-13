import type { SafeActionName, SafeActionResponse } from '../types/api'
import { actions } from './actionDefinitions'

type ActionPanelProps = {
  dryRun: boolean
  isPending: boolean
  latestResult: SafeActionResponse | null
  latestError: string | null
  onRunAction: (action: SafeActionName) => void
}

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
            sync/cleanup 不會建立 live offer；Cancel 與 Run Once 會遵守後端 safety guard。
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
