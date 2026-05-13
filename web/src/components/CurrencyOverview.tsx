import type { CurrencyDetail } from '../types/api'
import { formatAmount, formatRate } from '../utils/number'

type CurrencyOverviewProps = {
  details: CurrencyDetail[]
}

export function CurrencyOverview({ details }: CurrencyOverviewProps) {
  return (
    <section className="currency-overview" id="coins">
      <div className="section-heading compact">
        <div>
          <h2>幣種明細總覽</h2>
          <p>彙整目前放貸、未成交委託、累積收益與最新市場利率。</p>
        </div>
        <span>{details.length} coins</span>
      </div>

      {details.length ? (
        <div className="currency-table-scroll">
          <table className="currency-table">
            <thead>
              <tr>
                <th>幣種</th>
                <th>目前放貸</th>
                <th>放貸筆數</th>
                <th>未成交委託</th>
                <th>委託數</th>
                <th>平均日利率</th>
                <th>市場日利率</th>
                <th>累積收益</th>
              </tr>
            </thead>
            <tbody>
              {details.map((detail) => (
                <tr key={detail.currency}>
                  <td>{detail.currency}</td>
                  <td>{amount(detail.active_amount)}</td>
                  <td>{detail.active_loan_count}</td>
                  <td>{amount(detail.open_offer_amount)}</td>
                  <td>{detail.open_offer_count}</td>
                  <td>{rate(detail.average_daily_rate)}</td>
                  <td>{rate(detail.latest_market_rate)}</td>
                  <td>{amount(detail.total_earned)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-hint padded">目前沒有可彙整的幣種資料。</p>
      )}
    </section>
  )
}

const rate = formatRate
const amount = formatAmount
