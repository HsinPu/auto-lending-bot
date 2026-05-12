import type {
  ActiveLoan,
  BotRun,
  DashboardData,
  EarningsSummary,
  LendingHistoryEntry,
  LoanOffer,
  MarketRate,
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
    marketRates,
    settings,
  ] = await Promise.all([
    getJson<StatusResponse>('/api/status'),
    getJson<BotRun[]>('/api/runs'),
    getJson<LoanOffer[]>('/api/offers'),
    getJson<LoanOffer[]>('/api/open-offers'),
    getJson<ActiveLoan[]>('/api/active-loans'),
    getJson<LendingHistoryEntry[]>('/api/lending-history'),
    getJson<EarningsSummary[]>('/api/earnings'),
    getJson<MarketRate[]>('/api/market-rates'),
    getJson<SettingsResponse>('/api/settings'),
  ])

  return {
    status,
    runs,
    offers,
    openOffers,
    activeLoans,
    lendingHistory,
    earnings,
    marketRates,
    settings,
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`)
  }

  return response.json() as Promise<T>
}
