import type { EarningsSummary, LoanOffer, MarketRate } from '../types/api'

type MiniChartsProps = {
  earnings: EarningsSummary[]
  marketRates: MarketRate[]
  offers: LoanOffer[]
}

export function MiniCharts({ earnings, marketRates, offers }: MiniChartsProps) {
  const maxEarned = Math.max(...earnings.map((row) => Math.abs(row.total_earned)), 0)
  const maxRate = Math.max(...marketRates.map((row) => row.daily_rate), 0)
  const offerStatuses = countByStatus(offers)

  return (
    <section className="chart-grid" id="charts" aria-label="Visual summaries">
      <article className="chart-card">
        <h2>收益分布</h2>
        <p>依幣種比較累積收益。</p>
        <div className="bar-list">
          {earnings.length === 0 ? <span className="empty-hint">尚無收益資料</span> : null}
          {earnings.map((row) => (
            <MetricBar
              key={row.currency}
              label={row.currency}
              value={row.total_earned}
              ratio={maxEarned > 0 ? Math.abs(row.total_earned) / maxEarned : 0}
            />
          ))}
        </div>
      </article>

      <article className="chart-card">
        <h2>最近市場利率</h2>
        <p>最新 lendbook 日利率快照。</p>
        <div className="bar-list">
          {marketRates.length === 0 ? <span className="empty-hint">尚無市場資料</span> : null}
          {marketRates.slice(0, 8).map((row) => (
            <MetricBar
              key={`${row.id}-${row.currency}`}
              label={row.currency}
              value={row.daily_rate * 100}
              suffix="%"
              ratio={maxRate > 0 ? row.daily_rate / maxRate : 0}
            />
          ))}
        </div>
      </article>

      <article className="chart-card">
        <h2>委託狀態</h2>
        <p>本地 offer 狀態分布。</p>
        <div className="status-pills">
          {offerStatuses.length === 0 ? <span className="empty-hint">尚無委託資料</span> : null}
          {offerStatuses.map(([status, count]) => (
            <span key={status}>
              {status}: <strong>{count}</strong>
            </span>
          ))}
        </div>
      </article>
    </section>
  )
}

function MetricBar({
  label,
  value,
  ratio,
  suffix = '',
}: {
  label: string
  value: number
  ratio: number
  suffix?: string
}) {
  return (
    <div className="metric-bar">
      <div>
        <span>{label}</span>
        <strong>
          {value.toPrecision(6)}{suffix}
        </strong>
      </div>
      <div className="bar-track">
        <i style={{ width: `${Math.max(ratio * 100, 2)}%` }} />
      </div>
    </div>
  )
}

function countByStatus(offers: LoanOffer[]): Array<[string, number]> {
  const counts = new Map<string, number>()
  for (const offer of offers) {
    const status = offer.status ?? 'unknown'
    counts.set(status, (counts.get(status) ?? 0) + 1)
  }
  return [...counts.entries()].sort(([left], [right]) => left.localeCompare(right))
}
