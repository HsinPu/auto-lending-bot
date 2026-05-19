export type StatusResponse = {
  label: string
  profile: BotProfile
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

export type BotProfile = {
  id: string
  name: string
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
  bot_job_id: number | null
  bot_job: BotJob | null
  started_at: string | null
  restored_at: string | null
  last_run_at: string | null
  loops_completed: number
  last_error: string | null
}

export type BotJob = {
  id: number
  profile_id: string
  status: string
  mode: string
  started_at: string
  stopped_at: string | null
  stop_reason: string | null
  loops_completed: number
  last_run_id: number | null
  last_error: string | null
  snapshot_summary?: BotJobSnapshotSummary
}

export type BotJobSnapshotSummary = {
  exchange: string
  dry_run: boolean
  bot_sleep_seconds: number
  bot_inactive_sleep_seconds: number
  min_daily_rate: number
  max_daily_rate: number
  max_total_lend_amount: number | null
  max_single_offer_amount: number | null
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
  dry_run: number
  source: string
  synced_at: string
}

export type EarningsSummary = {
  currency: string
  today_earned: number
  yesterday_earned: number
  total_earned: number
  dry_run: number
  source: string
}

export type ConvertedEarnings = {
  currency: string
  output_currency: string
  total_earned: number
  dry_run: number
  source: string
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
  profile: BotProfile
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
  scope: ManagedSettingScope
}

export type ManagedSettingValue = {
  key: string
  value: string
  value_type: string
  is_secret: number
  updated_at: string
  is_set?: boolean
  scope?: ManagedSettingScope
}

export type ManagedSettingScope = 'global' | 'profile' | 'profile_secret' | 'profile_safety'

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

export type StrategyRateCandidate = {
  daily_rate: number
  annual_rate: number
  fill_probability: number
  expected_score: number
  meets_min_probability: boolean
  selected: boolean
  selection_role: string
  source: string
}

export type MarketRegime = {
  label?: string
  trend?: string
  volatility?: string
  current_daily_rate?: number
  short_average_daily_rate?: number | null
  long_average_daily_rate?: number | null
  sample_count?: number
  reason?: string
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
  rate_candidates: StrategyRateCandidate[]
  market_regime: MarketRegime | null
  allocation_mode?: string
  allocation_reason?: string
  stale_reprice_minutes?: number | null
  reason: string
}

export type StrategyPerformanceGroup = {
  label: string
  total_offers: number
  filled_offers: number
  canceled_offers: number
  open_offers: number
  pending_offers: number
  failed_offers: number
  total_amount: number
  filled_amount: number
  canceled_amount: number
  open_amount: number
  fill_rate: number
  amount_fill_rate: number
  cancel_rate: number
  average_daily_rate: number | null
  average_annual_rate: number | null
  average_time_to_fill_seconds: number | null
  average_reprice_count: number | null
  average_expected_fill_probability: number | null
  average_expected_score: number | null
  actual_vs_expected_fill_delta: number | null
}

export type StrategyPerformanceSummary = {
  overall: StrategyPerformanceGroup
  by_currency: StrategyPerformanceGroup[]
  by_risk_level: StrategyPerformanceGroup[]
}

export type RunDecisionHistory = {
  decisions: StrategyDecision[]
  steps: BotRunStep[]
}

export type RunPreviewSummary = {
  decision_count: number
  total_offer_count: number
  total_offer_amount: number
  currencies_with_offers: string[]
  blocked_currency_count: number
}

export type RunPreviewResponse = {
  action: 'run-preview'
  ok: boolean
  mode: 'dry_run' | 'live'
  exchange: string
  profile: BotProfile
  requires_live_confirmation: boolean
  safety_error: string | null
  live_readiness: LiveReadinessSection
  summary: RunPreviewSummary
  decisions: StrategyDecision[]
  warnings: string[]
}

export type DashboardData = {
  status: StatusResponse
  liveReadiness: LiveReadiness
  jobs: BotJob[]
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
  strategyPerformance: StrategyPerformanceSummary
}

export type SafeActionName =
  | 'smoke-exchange'
  | 'sync-history'
  | 'sync-open-offers'
  | 'transfer-preview'
  | 'transfer-funds'
  | 'cancel-open-offer'
  | 'cancel-open-offers'
  | 'record-market-analysis'
  | 'run-preview'
  | 'start-market-analysis'
  | 'stop-market-analysis'
  | 'cleanup'
  | 'reset-dry-run-records'
  | 'run-once'
  | 'start-loop'
  | 'stop-job'
  | 'stop-loop'

export type SafeActionResponse = {
  action: SafeActionName
  ok: boolean
  [key: string]: unknown
}
