import type { CurrencyDetail } from '../types/api'

type EarningsForecastProps = {
  details: CurrencyDetail[]
}

export function EarningsForecast({ details }: EarningsForecastProps) {
  const rows = details
    .map((detail) => ({
      currency: detail.currency,
      hourly: estimate(detail, 1 / 24),
      daily: estimate(detail, 1),
      weekly: estimate(detail, 7),
      monthly: estimate(detail, 30),
      yearly: estimate(detail, 365),
    }))
    .filter((row) => row.yearly > 0)

  return (
    <section className="forecast-panel">
      <div className="section-heading compact">
        <div>
          <h2>收益時間推估</h2>
          <p>用目前放貸本金與平均日利率估算，不混合不同幣種加總。</p>
        </div>
        <span>{rows.length} active</span>
      </div>

      {rows.length ? (
        <div className="forecast-grid">
          {rows.map((row) => (
            <article className="forecast-card" key={row.currency}>
              <strong>{row.currency}</strong>
              <div className="forecast-metrics">
                <Metric label="Hour" value={amount(row.hourly)} />
                <Metric label="Day" value={amount(row.daily)} />
                <Metric label="Week" value={amount(row.weekly)} />
                <Metric label="Month" value={amount(row.monthly)} />
                <Metric label="Year" value={amount(row.yearly)} />
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-hint padded">目前沒有 active loan 可推估收益。</p>
      )}
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  )
}

function estimate(detail: CurrencyDetail, days: number) {
  return detail.active_amount * detail.average_daily_rate * days
}

const amount = (value: number) => value.toPrecision(8)
