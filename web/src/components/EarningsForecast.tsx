import type { CurrencyDetail } from '../types/api'
import { formatAmount, formatPercent } from '../utils/number'

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
        <span>{rows.length} 個放貸中幣別</span>
      </div>

      {rows.length ? (
        <ul className="forecast-list">
          {rows.map((row) => (
            <li className="forecast-row" key={row.currency}>
              <div className="forecast-row-header">
                <p className="eyebrow">幣種</p>
                <strong>{row.currency}</strong>
              </div>
              <div className="forecast-metrics">
                <Metric label="放貸中" value={amount(row.activeAmount)} />
                <Metric label="平均日利率" value={percent(row.averageDailyRate)} />
                <Metric label="扣費後日利率" value={percent(row.netDailyRate)} />
                <Metric label="每小時" value={amount(row.hourly)} />
                <Metric label="每日" value={amount(row.daily)} />
                <Metric label="每週" value={amount(row.weekly)} />
                <Metric label="每月" value={amount(row.monthly)} />
                <Metric label="每年" value={amount(row.yearly)} />
                <Metric label="單利年化" value={percent(row.simpleYearlyRate)} />
                <Metric label="複利年化" value={percent(row.compoundYearlyRate)} />
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-hint padded">目前沒有放貸中資料可推估收益。</p>
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

const amount = formatAmount
const percent = formatPercent
