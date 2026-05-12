import type {
  ActiveLoan,
  BotRun,
  ConvertedEarnings,
  DashboardData,
  CurrencyDetail,
  EarningsSummary,
  LendingHistoryEntry,
  LoanOffer,
  MarketRate,
  SafeActionName,
  SafeActionResponse,
  SettingsResponse,
  StatusResponse,
} from '../types/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export async function getStatus(): Promise<StatusResponse> {
  return getJson<StatusResponse>('/api/status')
}

export async function getDashboardData(): Promise<DashboardData> {
  const [
    status,
    runs,
    offers,
    openOffers,
    activeLoans,
    lendingHistory,
    earnings,
    convertedEarnings,
    marketRates,
    settings,
    currencyDetails,
  ] = await Promise.all([
    getJson<StatusResponse>('/api/status'),
    getJson<BotRun[]>('/api/runs'),
    getJson<LoanOffer[]>('/api/offers'),
    getJson<LoanOffer[]>('/api/open-offers'),
    getJson<ActiveLoan[]>('/api/active-loans'),
    getJson<LendingHistoryEntry[]>('/api/lending-history'),
    getJson<EarningsSummary[]>('/api/earnings'),
    getJson<ConvertedEarnings[]>('/api/converted-earnings'),
    getJson<MarketRate[]>('/api/market-rates'),
    getJson<SettingsResponse>('/api/settings'),
    getJson<CurrencyDetail[]>('/api/currency-details'),
  ])

  return {
    status,
    runs,
    offers,
    openOffers,
    activeLoans,
    lendingHistory,
    earnings,
    convertedEarnings,
    marketRates,
    settings,
    currencyDetails,
  }
}

export async function runSafeAction(
  action: SafeActionName,
  options: { confirmLive?: boolean } = {},
): Promise<SafeActionResponse> {
  const body = options.confirmLive ? { confirm_live: true } : undefined
  return postJson<SafeActionResponse>(`/api/actions/${action}`, body)
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`)
  }

  return response.json() as Promise<T>
}

async function postJson<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail ?? `API request failed with ${response.status}`)
  }

  return response.json() as Promise<T>
}
