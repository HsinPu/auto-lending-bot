import type { CurrencyDetail } from '../types/api'

type EarningsForecastProps = {
  details: CurrencyDetail[]
}

export function EarningsForecast({ details }: EarningsForecastProps) {
  const rows = details
    .map((detail) => ({
      currency: detail.currency,
      activeAmount: detail.active_amount,
      averageDailyRate: detail.average_daily_rate,
      netDailyRate: netDailyRate(detail),
      hourly: estimate(detail, 1 / 24),
      daily: estimate(detail, 1),
      weekly: estimate(detail, 7),
      monthly: estimate(detail, 30),
      yearly: estimate(detail, 365),
      simpleYearlyRate: netDailyRate(detail) * 365,
      compoundYearlyRate: Math.pow(1 + netDailyRate(detail), 365) - 1,
    }))
    .filter((row) => row.yearly > 0)

  return (
    <section className="forecast-panel" id="forecast">
      <div className="section-heading compact">
        <div>
          <h2>收益時間推估</h2>
          <p>用目前放貸本金與平均日利率估算，預設扣除 15% 交易所費用。</p>
        </div>
        <span>{rows.length} active</span>
      </div>

      {rows.length ? (
        <div className="forecast-grid">
          {rows.map((row) => (
            <article className="forecast-card" key={row.currency}>
              <strong>{row.currency}</strong>
              <div className="forecast-metrics">
                <Metric label="Active" value={amount(row.activeAmount)} />
                <Metric label="Avg day" value={percent(row.averageDailyRate)} />
                <Metric label="Net day" value={percent(row.netDailyRate)} />
                <Metric label="Hour" value={amount(row.hourly)} />
                <Metric label="Day" value={amount(row.daily)} />
                <Metric label="Week" value={amount(row.weekly)} />
                <Metric label="Month" value={amount(row.monthly)} />
                <Metric label="Year" value={amount(row.yearly)} />
                <Metric label="APR" value={percent(row.simpleYearlyRate)} />
                <Metric label="APY" value={percent(row.compoundYearlyRate)} />
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
  return detail.active_amount * netDailyRate(detail) * days
}

function netDailyRate(detail: CurrencyDetail) {
  return detail.average_daily_rate * 0.85
}

const amount = (value: number) => value.toPrecision(8)
const percent = (value: number) => `${(value * 100).toFixed(4)}%`
