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

export type BotRun = {
  id: number
  started_at: string
  finished_at: string | null
  status: string
  dry_run: number
  message: string
}

export type LoanOffer = {
  id: number
  bot_run_id?: number
  currency: string
  amount: number
  daily_rate: number
  duration_days: number
  status?: string
  dry_run?: number
  external_offer_id: string | null
  message?: string
  created_at?: string
  captured_at?: string
}

export type ActiveLoan = {
  id: number
  currency: string
  amount: number
  daily_rate: number
  duration_days: number
  external_loan_id: string | null
  captured_at: string
}

export type LendingHistoryEntry = {
  id: number
  external_entry_id: string
  currency: string
  amount: number
  daily_rate: number
  duration_days: number
  interest: number
  fee: number
  earned: number
  opened_at: string
  closed_at: string
  synced_at: string
}

export type EarningsSummary = {
  currency: string
  today_earned: number
  yesterday_earned: number
  total_earned: number
}

export type MarketRate = {
  id: number
  currency: string
  daily_rate: number
  available_amount: number
  captured_at: string
}

export type SettingsResponse = {
  label: string
  exchange: string
  dry_run: boolean
  allow_live_trading: boolean
  bitfinex_enable_live_offers: boolean
  smoke_test_currency: string
  strategy_debug: boolean
  strategy: Record<string, string | number | boolean | null>
}

export type CurrencyDetail = {
  currency: string
  active_amount: number
  open_offer_amount: number
  average_daily_rate: number
  latest_market_rate: number
  total_earned: number
  active_loan_count: number
  open_offer_count: number
}

export type DashboardData = {
  status: StatusResponse
  runs: BotRun[]
  offers: LoanOffer[]
  openOffers: LoanOffer[]
  activeLoans: ActiveLoan[]
  lendingHistory: LendingHistoryEntry[]
  earnings: EarningsSummary[]
  marketRates: MarketRate[]
  settings: SettingsResponse
  currencyDetails: CurrencyDetail[]
}

export type SafeActionName =
  | 'smoke-exchange'
  | 'sync-history'
  | 'sync-open-offers'
  | 'cancel-open-offers'
  | 'cleanup'
  | 'run-once'

export type SafeActionResponse = {
  action: SafeActionName
  ok: boolean
  [key: string]: string | number | boolean
}
