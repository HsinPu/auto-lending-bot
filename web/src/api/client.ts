import type {
  ActiveLoan,
  BotRun,
  BotRunStep,
  ConvertedEarnings,
  DashboardData,
  CurrencyDetail,
  EarningsSummary,
  LendingHistoryEntry,
  LiveReadiness,
  LoanOffer,
  MarketAnalysisRate,
  MarketAnalysisStatus,
  MarketRate,
  ManagedSettingsExport,
  ManagedSettingsData,
  ManagedSettingDefinition,
  ManagedSettingValue,
  RunDecisionHistory,
  SafeActionName,
  SafeActionResponse,
  SettingsResponse,
  StatusResponse,
  StrategyDecision,
} from '../types/api'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export async function getStatus(): Promise<StatusResponse> {
  return getJson<StatusResponse>('/api/status')
}

export async function getDashboardData(): Promise<DashboardData> {
  const [
    status,
    liveReadiness,
    runs,
    offers,
    openOffers,
    activeLoans,
    lendingHistory,
    earnings,
    convertedEarnings,
    marketRates,
    marketAnalysisRates,
    marketAnalysisStatus,
    settings,
    currencyDetails,
    strategyDecisions,
  ] = await Promise.all([
    getJson<StatusResponse>('/api/status'),
    getJson<LiveReadiness>('/api/live-readiness'),
    getJson<BotRun[]>('/api/runs'),
    getJson<LoanOffer[]>('/api/offers'),
    getJson<LoanOffer[]>('/api/open-offers'),
    getJson<ActiveLoan[]>('/api/active-loans'),
    getJson<LendingHistoryEntry[]>('/api/lending-history'),
    getJson<EarningsSummary[]>('/api/earnings'),
    getJson<ConvertedEarnings[]>('/api/converted-earnings'),
    getJson<MarketRate[]>('/api/market-rates'),
    getJson<MarketAnalysisRate[]>('/api/market-analysis-rates'),
    getJson<MarketAnalysisStatus[]>('/api/market-analysis-status'),
    getJson<SettingsResponse>('/api/settings'),
    getJson<CurrencyDetail[]>('/api/currency-details'),
    getJson<StrategyDecision[]>('/api/strategy-decisions'),
  ])

  return {
    status,
    liveReadiness,
    runs,
    offers,
    openOffers,
    activeLoans,
    lendingHistory,
    earnings,
    convertedEarnings,
    marketRates,
    marketAnalysisRates,
    marketAnalysisStatus,
    settings,
    currencyDetails,
    strategyDecisions,
  }
}

export async function runSafeAction(
  action: SafeActionName,
  options: { adminToken?: string; confirmLive?: boolean } = {},
): Promise<SafeActionResponse> {
  const body = options.confirmLive ? { confirm_live: true } : undefined
  return postJson<SafeActionResponse>(`/api/actions/${action}`, body, options.adminToken)
}

export async function getManagedSettings(): Promise<ManagedSettingsData> {
  const [schema, values] = await Promise.all([
    getJson<ManagedSettingDefinition[]>('/api/settings/schema'),
    getJson<Record<string, ManagedSettingValue>>('/api/settings/values'),
  ])

  return { schema, values }
}

export async function getRunDecisionHistory(botRunId: number): Promise<RunDecisionHistory> {
  const [decisions, steps] = await Promise.all([
    getJson<StrategyDecision[]>(`/api/runs/${botRunId}/decisions`),
    getJson<BotRunStep[]>(`/api/runs/${botRunId}/steps`),
  ])

  return { decisions, steps }
}

export async function updateManagedSettings(
  values: Record<string, string>,
  adminToken: string,
): Promise<{ ok: boolean; changed_count: number }> {
  return putJson<{ ok: boolean; changed_count: number }>(
    '/api/settings/values',
    { values },
    adminToken,
  )
}

export async function resetManagedSetting(
  key: string | null,
  adminToken: string,
): Promise<{ ok: boolean; reset_count: number }> {
  return postJson<{ ok: boolean; reset_count: number }>(
    '/api/settings/reset',
    key ? { key } : {},
    adminToken,
  )
}

export async function exportManagedSettings(): Promise<ManagedSettingsExport> {
  return getJson<ManagedSettingsExport>('/api/settings/export')
}

export async function importManagedSettings(
  values: Record<string, string>,
  adminToken: string,
): Promise<{ ok: boolean; changed_count: number }> {
  return postJson<{ ok: boolean; changed_count: number }>(
    '/api/settings/import',
    { values },
    adminToken,
  )
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`)
  }

  return response.json() as Promise<T>
}

async function postJson<T>(
  path: string,
  body?: Record<string, unknown>,
  adminToken?: string,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: requestHeaders(body, adminToken),
    body: body ? JSON.stringify(body) : undefined,
  })
  return parseJsonResponse<T>(response)
}

async function putJson<T>(
  path: string,
  body: Record<string, unknown>,
  adminToken?: string,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'PUT',
    headers: requestHeaders(body, adminToken),
    body: JSON.stringify(body),
  })
  return parseJsonResponse<T>(response)
}

function requestHeaders(body?: Record<string, unknown>, adminToken?: string): HeadersInit | undefined {
  const headers: Record<string, string> = {}
  if (body) {
    headers['Content-Type'] = 'application/json'
  }
  if (adminToken) {
    headers.Authorization = `Bearer ${adminToken}`
  }

  return Object.keys(headers).length ? headers : undefined
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail ?? `API request failed with ${response.status}`)
  }

  return response.json() as Promise<T>
}
