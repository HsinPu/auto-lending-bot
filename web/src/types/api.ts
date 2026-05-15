export type StatusResponse = {
  label: string
  database: string
  exchange: string
  dry_run: boolean
  live_trading_allowed: boolean
  bot_loop: BotLoopStatus
  market_analysis_collection: MarketAnalysisCollectionStatus
  settings_runtime: {
    hot_reload: boolean
    managed_override_count: number
    last_updated_at: string | null
  }
  counts: {
    bot_runs: number
    loan_offers: number
    open_loan_offers: number
    active_loans: number
    lending_history: number
    market_rates: number
    market_analysis_rates: number
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

export type MarketAnalysisCollectionStatus = {
  running: boolean
  started_at: string | null
  last_run_at: string | null
  loops_completed: number
  last_changed_count: number
  last_error: string | null
}

export type BotLoopStatus = {
  running: boolean
  started_at: string | null
  last_run_at: string | null
  loops_completed: number
  last_error: string | null
}

export type LiveReadinessItem = {
  label: string
  ok: boolean
}

export type LiveReadinessSection = {
  ready: boolean
  items: LiveReadinessItem[]
  missing: string[]
}

export type LiveReadiness = {
  live_offers: LiveReadinessSection
  live_transfers: LiveReadinessSection
  note: string
}

export type BotRun = {
  id: number
  started_at: string
  finished_at: string | null
  status: string
  dry_run: number
  message: string
}

export type BotRunStep = {
  id: number
  bot_run_id: number
  step_key: string
  label: string
  status: string
  started_at: string
  finished_at: string | null
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

export type ConvertedEarnings = {
  currency: string
  output_currency: string
  total_earned: number
  converted_total_earned: number | null
  conversion_available: boolean
}

export type MarketRate = {
  id: number
  currency: string
  daily_rate: number
  available_amount: number
  captured_at: string
}

export type MarketAnalysisRate = {
  id: number
  currency: string
  level: number
  daily_rate: number
  available_amount: number
  captured_at: string
}

export type MarketAnalysisStatus = {
  currency: string
  method: string
  sample_count: number
  top_level_sample_count: number
  min_samples: number
  max_age_seconds: number
  latest_captured_at: string | null
  is_stale: boolean
  has_enough_samples: boolean
  suggested_min_daily_rate: number | null
  reason: string
}

export type SettingsResponse = {
  label: string
  exchange: string
  dry_run: boolean
  allow_live_trading: boolean
  bitfinex_enable_live_offers: boolean
  output_currency: string
  display_timezone: string
  market_analysis_currencies: string[]
  market_analysis_interval_seconds: number
  market_analysis_levels: number
  market_analysis_suggested_min_daily_rate: number | null
  effective_min_daily_rate: number
  smoke_test_currency: string
  strategy_debug: boolean
  strategy: Record<string, string | number | boolean | null>
}

export type ManagedSettingDefinition = {
  key: string
  category: string
  value_type: string
  default: string
  secret: boolean
  danger_level: 'normal' | 'high' | 'critical'
  hot_reload: boolean
  description: string
  choices: string[]
}

export type ManagedSettingValue = {
  key: string
  value: string
  value_type: string
  is_secret: number
  updated_at: string
  is_set?: boolean
}

export type ManagedSettingsData = {
  schema: ManagedSettingDefinition[]
  values: Record<string, ManagedSettingValue>
}

export type ManagedSettingsExport = {
  version: number
  includes_secrets: boolean
  values: Record<string, string>
  excluded_secret_keys: string[]
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

export type StrategyDecisionOffer = {
  currency: string
  amount: number
  daily_rate: number
  duration_days: number
  external_offer_id: string
}

export type StrategyDecision = {
  currency: string
  balance: number
  active_amount: number
  open_offer_amount: number
  best_market_rate: number
  configured_min_daily_rate: number
  suggested_min_daily_rate: number | null
  effective_min_daily_rate: number
  max_daily_rate: number
  max_to_lend: number | null
  max_percent_to_lend: number
  max_active_amount: number | null
  offer_count: number
  offers: StrategyDecisionOffer[]
  reason: string
}

export type DashboardData = {
  status: StatusResponse
  liveReadiness: LiveReadiness
  runs: BotRun[]
  offers: LoanOffer[]
  openOffers: LoanOffer[]
  activeLoans: ActiveLoan[]
  lendingHistory: LendingHistoryEntry[]
  earnings: EarningsSummary[]
  convertedEarnings: ConvertedEarnings[]
  marketRates: MarketRate[]
  marketAnalysisRates: MarketAnalysisRate[]
  marketAnalysisStatus: MarketAnalysisStatus[]
  settings: SettingsResponse
  currencyDetails: CurrencyDetail[]
  strategyDecisions: StrategyDecision[]
}

export type SafeActionName =
  | 'smoke-exchange'
  | 'sync-history'
  | 'sync-open-offers'
  | 'transfer-preview'
  | 'transfer-funds'
  | 'cancel-open-offers'
  | 'record-market-analysis'
  | 'start-market-analysis'
  | 'stop-market-analysis'
  | 'cleanup'
  | 'reset-dry-run-records'
  | 'run-once'
  | 'start-loop'
  | 'stop-loop'

export type SafeActionResponse = {
  action: SafeActionName
  ok: boolean
  [key: string]: unknown
}
