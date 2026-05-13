import type { LendingHistoryEntry } from '../types/api'
import { formatTimestampDay } from '../utils/time'

type ProfitChartsProps = {
  history: LendingHistoryEntry[]
  timeZone: string
}

type ProfitPoint = {
  day: string
  earned: number
  cumulative: number
}

export function ProfitCharts({ history, timeZone }: ProfitChartsProps) {
  const points = buildProfitPoints(history, timeZone)
  const maxDaily = Math.max(...points.map((point) => point.earned), 0)
  const maxCumulative = Math.max(...points.map((point) => point.cumulative), 0)

  return (
    <section className="profit-panel" id="profits">
      <div className="section-heading compact">
        <div>
          <h2>收益圖表</h2>
          <p>依 lending history 的 close date 彙整每日收益與累積收益。</p>
        </div>
        <span>{points.length} days</span>
      </div>

      {points.length ? (
        <div className="profit-chart-grid">
          <ProfitBarChart title="每日收益" points={points} metric="earned" max={maxDaily} />
          <ProfitBarChart title="累積收益" points={points} metric="cumulative" max={maxCumulative} />
        </div>
      ) : (
        <p className="empty-hint padded">目前沒有 lending history 可繪製收益圖。</p>
      )}
    </section>
  )
}

function ProfitBarChart({
  title,
  points,
  metric,
  max,
}: {
  title: string
  points: ProfitPoint[]
  metric: 'earned' | 'cumulative'
  max: number
}) {
  return (
    <article className="profit-chart-card">
      <h3>{title}</h3>
      <div className="profit-bars" aria-label={title}>
        {points.map((point) => {
          const value = point[metric]
          const height = max > 0 ? Math.max(8, (value / max) * 100) : 0
          return (
            <div className="profit-bar" key={`${metric}-${point.day}`}>
              <i style={{ height: `${height}%` }} title={`${point.day}: ${amount(value)}`} />
              <span>{point.day.slice(5)}</span>
            </div>
          )
        })}
      </div>
    </article>
  )
}

function buildProfitPoints(history: LendingHistoryEntry[], timeZone: string): ProfitPoint[] {
  const daily = new Map<string, number>()
  for (const entry of history) {
    const day = formatTimestampDay(entry.closed_at, timeZone)
    daily.set(day, (daily.get(day) ?? 0) + entry.earned)
  }

  let cumulative = 0
  return [...daily.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([day, earned]) => {
      cumulative += earned
      return { day, earned, cumulative }
    })
}

const amount = (value: number) => value.toPrecision(8)
