import type { ConvertedEarnings } from '../types/api'

type ConvertedEarningsPanelProps = {
  rows: ConvertedEarnings[]
  btcUnit: 'BTC' | 'mBTC' | 'Bits' | 'Satoshi'
}

export function ConvertedEarningsPanel({ rows, btcUnit }: ConvertedEarningsPanelProps) {
  const outputCurrency = rows[0]?.output_currency ?? 'BTC'

  return (
    <section className="converted-earnings-panel">
      <div className="section-heading compact">
        <div>
          <h2>換算收益</h2>
          <p>依設定的 output currency 顯示累積收益換算。</p>
        </div>
        <span>{outputCurrency}</span>
      </div>
      {rows.length ? (
        <div className="converted-earnings-grid">
          {rows.map((row) => (
            <article key={row.currency}>
              <strong>{row.currency}</strong>
              <span>原幣 {displayAmount(row.total_earned, row.currency, btcUnit)}</span>
              <b>
                {row.conversion_available && row.converted_total_earned !== null
                  ? displayAmount(row.converted_total_earned, row.output_currency, btcUnit)
                  : 'unavailable'}
              </b>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-hint padded">目前沒有收益可換算。</p>
      )}
    </section>
  )
}

function displayAmount(
  value: number,
  currency: string,
  btcUnit: ConvertedEarningsPanelProps['btcUnit'],
) {
  if (currency !== 'BTC') {
    return `${amount(value)} ${currency}`
  }

  const multipliers = {
    BTC: 1,
    mBTC: 1000,
    Bits: 1000000,
    Satoshi: 100000000,
  }
  return `${amount(value * multipliers[btcUnit])} ${btcUnit}`
}

const amount = (value: number) => value.toPrecision(8)
