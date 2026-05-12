import type { ConvertedEarnings } from '../types/api'

type ConvertedEarningsPanelProps = {
  rows: ConvertedEarnings[]
}

export function ConvertedEarningsPanel({ rows }: ConvertedEarningsPanelProps) {
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
              <span>原幣 {amount(row.total_earned)}</span>
              <b>
                {row.conversion_available && row.converted_total_earned !== null
                  ? `${amount(row.converted_total_earned)} ${row.output_currency}`
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

const amount = (value: number) => value.toPrecision(8)
