import type { BotRun, LoanOffer, SafeActionResponse } from '../types/api'

type ActivityLogProps = {
  runs: BotRun[]
  offers: LoanOffer[]
  latestResult: SafeActionResponse | null
  latestError: string | null
}

type ActivityItem = {
  id: string
  time: string
  title: string
  detail: string
  tone?: 'ok' | 'error'
}

export function ActivityLog({ runs, offers, latestResult, latestError }: ActivityLogProps) {
  const items = buildActivityItems({ runs, offers, latestResult, latestError })

  return (
    <section className="activity-panel">
      <div className="section-heading compact">
        <div>
          <h2>活動紀錄</h2>
          <p>最近 action、bot run 與 lending offer 狀態。</p>
        </div>
        <span>{items.length} logs</span>
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
}: ActivityLogProps): ActivityItem[] {
  const actionItems: ActivityItem[] = []
  if (latestError) {
    actionItems.push({
      id: 'action-error',
      time: 'now',
      title: 'Action failed',
      detail: latestError,
      tone: 'error',
    })
  }
  if (latestResult) {
    actionItems.push({
      id: 'action-result',
      time: 'now',
      title: `Action completed: ${latestResult.action}`,
      detail: JSON.stringify(latestResult),
      tone: 'ok',
    })
  }

  const runItems: ActivityItem[] = runs.slice(0, 5).map((run) => ({
    id: `run-${run.id}`,
    time: formatTime(run.finished_at ?? run.started_at),
    title: `Run #${run.id} ${run.status}`,
    detail: run.message || 'No message',
    tone: run.status === 'completed' ? 'ok' : run.status === 'failed' ? 'error' : undefined,
  }))

  const offerItems: ActivityItem[] = offers.slice(0, 5).map((offer) => ({
    id: `offer-${offer.id}`,
    time: formatTime(offer.created_at),
    title: `${offer.currency} offer ${offer.status ?? 'recorded'}`,
    detail: `${amount(offer.amount)} at ${rate(offer.daily_rate)} for ${offer.duration_days} days`,
    tone: offer.status === 'failed' ? 'error' : 'ok',
  }))

  return [...actionItems, ...runItems, ...offerItems].slice(0, 10)
}

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : '-'
}

const rate = (value: number) => `${(value * 100).toFixed(4)}%`
const amount = (value: number) => value.toPrecision(8)
