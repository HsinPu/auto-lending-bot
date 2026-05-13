import type { BotRun, LoanOffer, SafeActionResponse } from '../types/api'
import { formatAmount, formatRate } from '../utils/number'
import { formatTimestamp } from '../utils/time'

type ActivityLogProps = {
  runs: BotRun[]
  offers: LoanOffer[]
  latestResult: SafeActionResponse | null
  latestError: string | null
  timeZone: string
}

type ActivityItem = {
  id: string
  time: string
  title: string
  detail: string
  tone?: 'ok' | 'error'
}

export function ActivityLog({ runs, offers, latestResult, latestError, timeZone }: ActivityLogProps) {
  const items = buildActivityItems({ runs, offers, latestResult, latestError, timeZone })

  return (
    <section className="activity-panel" id="logs">
      <div className="section-heading compact">
        <div>
          <h2>活動紀錄</h2>
          <p>最近操作、bot 執行與放貸委託狀態。</p>
        </div>
        <span>{items.length} 筆紀錄</span>
      </div>

      {items.length ? (
        <ol className="activity-list">
          {items.map((item) => (
            <li className={item.tone ?? ''} key={item.id}>
              <time>{item.time}</time>
              <div>
                <strong>{item.title}</strong>
                <p>{item.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="empty-hint padded">目前沒有活動紀錄。</p>
      )}
    </section>
  )
}

function buildActivityItems({
  runs,
  offers,
  latestResult,
  latestError,
  timeZone,
}: ActivityLogProps): ActivityItem[] {
  const actionItems: ActivityItem[] = []
  if (latestError) {
    actionItems.push({
      id: 'action-error',
      time: '現在',
      title: '操作失敗',
      detail: latestError,
      tone: 'error',
    })
  }
  if (latestResult) {
    actionItems.push({
      id: 'action-result',
      time: '現在',
      title: `操作完成：${actionLabel(latestResult.action)}`,
      detail: JSON.stringify(latestResult),
      tone: 'ok',
    })
  }

  const runItems: ActivityItem[] = runs.slice(0, 5).map((run) => ({
    id: `run-${run.id}`,
    time: formatTimestamp(run.finished_at ?? run.started_at, timeZone),
    title: `執行 #${run.id} ${statusLabel(run.status)}`,
    detail: run.message || '沒有訊息',
    tone: run.status === 'completed' ? 'ok' : run.status === 'failed' ? 'error' : undefined,
  }))

  const offerItems: ActivityItem[] = offers.slice(0, 5).map((offer) => ({
    id: `offer-${offer.id}`,
    time: formatTimestamp(offer.created_at, timeZone),
    title: `${offer.currency} 委託 ${statusLabel(offer.status ?? 'recorded')}`,
    detail: `${amount(offer.amount)}，日利率 ${rate(offer.daily_rate)}，${offer.duration_days} 天`,
    tone: offer.status === 'failed' ? 'error' : 'ok',
  }))

  return [...actionItems, ...runItems, ...offerItems].slice(0, 10)
}

const rate = formatRate
const amount = formatAmount

const statusLabels: Record<string, string> = {
  completed: '完成',
  failed: '失敗',
  running: '執行中',
  dry_run: '模擬',
  intent: '準備建立',
  created: '已建立',
  recorded: '已記錄',
}

const actionLabels: Record<string, string> = {
  'smoke-exchange': '連線檢查',
  'sync-history': '同步收益',
  'sync-open-offers': '同步委託',
  'transfer-preview': '轉帳預覽',
  'transfer-funds': '執行轉帳',
  'cancel-open-offers': '取消委託',
  'record-market-analysis': '記錄市場分析',
  cleanup: '清理資料',
  'run-once': '執行一次',
  'start-loop': '開始持續執行',
  'stop-loop': '停止持續執行',
}

function statusLabel(status: string): string {
  return statusLabels[status] ?? status
}

function actionLabel(action: string): string {
  return actionLabels[action] ?? action
}
