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
        <ul className="currency-list">
          {details.map((detail) => (
            <li className="currency-row" key={detail.currency}>
              <div className="currency-card-header">
                <div>
                  <p className="eyebrow">幣種</p>
                  <strong>{detail.currency}</strong>
                </div>
                <span>{detail.active_loan_count} 筆放貸中</span>
              </div>
              <dl>
                <Metric label="目前放貸" value={amount(detail.active_amount)} />
                <Metric label="未成交委託" value={amount(detail.open_offer_amount)} />
                <Metric label="平均日利率" value={rate(detail.average_daily_rate)} />
                <Metric label="市場日利率" value={rate(detail.latest_market_rate)} />
                <Metric label="累積收益" value={amount(detail.total_earned)} />
                <Metric label="委託數" value={String(detail.open_offer_count)} />
              </dl>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-hint padded">目前沒有可彙整的幣種資料。</p>
      )}
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

const rate = formatRate
const amount = formatAmount
