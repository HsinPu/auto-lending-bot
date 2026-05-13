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
        <div className="forecast-table-scroll">
          <table className="forecast-table">
            <thead>
              <tr>
                <th>幣種</th>
                <th>放貸中</th>
                <th>平均日利率</th>
                <th>扣費後日利率</th>
                <th>每小時</th>
                <th>每日</th>
                <th>每週</th>
                <th>每月</th>
                <th>每年</th>
                <th>單利年化</th>
                <th>複利年化</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.currency}>
                  <td>{row.currency}</td>
                  <td>{amount(row.activeAmount)}</td>
                  <td>{percent(row.averageDailyRate)}</td>
                  <td>{percent(row.netDailyRate)}</td>
                  <td>{amount(row.hourly)}</td>
                  <td>{amount(row.daily)}</td>
                  <td>{amount(row.weekly)}</td>
                  <td>{amount(row.monthly)}</td>
                  <td>{amount(row.yearly)}</td>
                  <td>{percent(row.simpleYearlyRate)}</td>
                  <td>{percent(row.compoundYearlyRate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-hint padded">目前沒有放貸中資料可推估收益。</p>
      )}
    </section>
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
