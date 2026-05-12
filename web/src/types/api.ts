export type StatusResponse = {
  label: string
  database: string
  exchange: string
  dry_run: boolean
  live_trading_allowed: boolean
  counts: {
    bot_runs: number
    loan_offers: number
    open_loan_offers: number
    active_loans: number
    lending_history: number
    market_rates: number
  }
  latest_run: null | {
    id: number
    started_at: string
    finished_at: string | null
    status: string
    dry_run: number
    message: string
  }
}
