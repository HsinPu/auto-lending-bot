import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { getDashboardData, runSafeAction } from '../api/client'
import { ActionPanel } from '../components/ActionPanel'
import { ActivityLog } from '../components/ActivityLog'
import { actions } from '../components/actionDefinitions'
import { ConvertedEarningsPanel } from '../components/ConvertedEarningsPanel'
import { CurrencyOverview } from '../components/CurrencyOverview'
import { DataTable } from '../components/DataTable'
import {
  DisplaySettingsModal,
  type DisplaySettings,
} from '../components/DisplaySettingsModal'
import { EarningsForecast } from '../components/EarningsForecast'
import { ManagedSettingsPanel } from '../components/ManagedSettingsPanel'
import { MiniCharts } from '../components/MiniCharts'
import { ProfitCharts } from '../components/ProfitCharts'
import { StatusCard } from '../components/StatusCard'
import { TopStatusBar } from '../components/TopStatusBar'
import type {
  ActiveLoan,
  BotRun,
  EarningsSummary,
  LendingHistoryEntry,
  LoanOffer,
  MarketAnalysisRate,
  MarketRate,
  SafeActionName,
  SafeActionResponse,
} from '../types/api'

export function DashboardPage() {
  const queryClient = useQueryClient()
  const [latestResult, setLatestResult] = useState<SafeActionResponse | null>(null)
  const [latestError, setLatestError] = useState<string | null>(null)
  const [displaySettings, setDisplaySettings] = useState<DisplaySettings>(loadDisplaySettings)
  const [adminToken, setAdminToken] = useState(loadAdminToken)
  const [activePage, setActivePage] = useState<PageKey>('overview')
  const { data, error, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboardData,
  })
  const actionMutation = useMutation({
    mutationFn: ({ action, confirmLive }: { action: SafeActionName; confirmLive?: boolean }) =>
      runSafeAction(action, { adminToken, confirmLive }),
    onSuccess: async (result) => {
      setLatestResult(result)
      setLatestError(null)
      await queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (mutationError) => {
      setLatestResult(null)
      setLatestError((mutationError as Error).message)
    },
  })
  const runAction = (action: SafeActionName, dryRun: boolean) => {
    const confirmLive = shouldConfirmLive(action, dryRun)
    if (confirmLive && !window.confirm('Live 模式會執行真實交易所操作。確定要繼續？')) {
      return
    }

    actionMutation.mutate({ action, confirmLive })
  }

  return (
    <>
      <TopStatusBar
        status={data?.status ?? null}
        isFetching={isFetching}
        lastRefreshed={data ? new Date() : null}
        onRefresh={() => void refetch()}
      />

      <main className={`shell with-top-bar ${displaySettings.compactLayout ? 'compact-layout' : ''}`}>
        <div className="dashboard-layout">
          <SidebarNavigation activePage={activePage} onChange={setActivePage} />

          <div className="dashboard-content">
            <section className="console-intro mika-intro">
              <div>
                <p className="eyebrow">Lending Console</p>
                <h1>{pageTitle(activePage, data?.status.label)}</h1>
                <p className="lede">{pageDescription(activePage)}</p>
              </div>
              <DisplaySettingsModal
                settings={displaySettings}
                onChange={(settings) => {
                  setDisplaySettings(settings)
                  localStorage.setItem(displaySettingsKey, JSON.stringify(settings))
                }}
              />
            </section>

      {isLoading ? <section className="status-skeleton">讀取 API 狀態中...</section> : null}
      {error ? <ErrorState message={(error as Error).message} /> : null}

      {data && activePage === 'overview' ? (
        <>
          <section className="quick-actions" aria-label="Primary bot controls">
            <div>
              <p className="eyebrow">Bot Controls</p>
              <h2>前端控制</h2>
              <p>
                目前是 {data.status.dry_run ? '模擬模式' : 'Live 模式'}。按鈕會呼叫後端 API，
                執行後自動更新資料。
              </p>
            </div>
            <div className="quick-action-buttons">
              {primaryActions.map((action) => {
                const item = actions.find((entry) => entry.action === action)
                if (!item) {
                  return null
                }

                return (
                  <button
                    key={item.action}
                    type="button"
                    className={`quick-action-button ${item.action === 'run-once' ? 'primary' : ''}`}
                    disabled={actionMutation.isPending}
                    onClick={() => runAction(item.action, data.status.dry_run)}
                  >
                    {actionMutation.isPending ? '執行中...' : item.label}
                  </button>
                )
              })}
            </div>
          </section>

          <ManagedSettingsPanel
            adminToken={adminToken}
            onAdminTokenChange={(token) => {
              setAdminToken(token)
              sessionStorage.setItem(adminTokenKey, token)
            }}
          />

          <div className="mika-console-layout">
            <div className="mika-main-column">
              <section className="status-grid" id="status" aria-label="Bot status summary">
                <StatusCard label="交易所" value={data.status.exchange} />
                <StatusCard
                  label="執行模式"
                  value={data.status.dry_run ? '模擬模式' : 'Live 模式'}
                  tone={data.status.dry_run ? 'safe' : 'danger'}
                />
                <StatusCard label="Bot runs" value={data.status.counts.bot_runs} />
                <StatusCard label="貸出委託" value={data.status.counts.loan_offers} />
                <StatusCard label="目前放貸中" value={data.status.counts.active_loans} />
                <StatusCard label="收益紀錄" value={data.status.counts.lending_history} />
                <StatusCard label="市場分析" value={data.status.counts.market_analysis_rates} />
                <StatusCard label="設定覆寫" value={data.status.settings_runtime.managed_override_count} />
              </section>

              <CurrencyOverview details={data.currencyDetails} />

              <ActivityLog
                runs={data.runs}
                offers={data.offers}
                latestResult={latestResult}
                latestError={latestError}
              />
            </div>

            <aside className="mika-side-column" aria-label="Console controls">
              <section className="settings-panel">
                <div>
                  <h2>策略設定預覽</h2>
                  <p>
                    {data.settings.smoke_test_currency} | strategy debug:{' '}
                    {data.settings.strategy_debug ? 'on' : 'off'}
                  </p>
                </div>
                <dl>
                  <div>
                    <dt>market_analysis_suggested_min_daily_rate</dt>
                    <dd>{rate(data.settings.market_analysis_suggested_min_daily_rate)}</dd>
                  </div>
                  <div>
                    <dt>effective_min_daily_rate</dt>
                    <dd>{rate(data.settings.effective_min_daily_rate)}</dd>
                  </div>
                </dl>
                <dl>
                  {Object.entries(data.settings.strategy).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              </section>

              <ActionPanel
                dryRun={data.status.dry_run}
                isPending={actionMutation.isPending}
                latestResult={latestResult}
                latestError={latestError}
                onRunAction={(action: SafeActionName) => runAction(action, data.status.dry_run)}
              />

              <EarningsForecast details={data.currencyDetails} />

              <ConvertedEarningsPanel
                rows={data.convertedEarnings}
                btcUnit={displaySettings.btcUnit}
              />
            </aside>
          </div>

          <section className="mika-chart-row" aria-label="Dashboard charts">
            <MiniCharts
              earnings={data.earnings}
              marketRates={data.marketRates}
              offers={data.offers}
            />

            <ProfitCharts history={data.lendingHistory} />
          </section>

          {displaySettings.showRawTables ? (
            <section className="raw-data-stack" aria-label="Raw API data">
              <div className="raw-data-anchor" id="raw-data" />
              <DataTable<BotRun>
                title="最近執行"
                description="Bot run 狀態與訊息。"
                rows={data.runs}
                columns={[
                  { key: 'id', label: '編號' },
                  { key: 'status', label: '狀態' },
                  { key: 'dry_run', label: '模擬' },
                  { key: 'started_at', label: '開始時間' },
                  { key: 'finished_at', label: '結束時間' },
                  { key: 'message', label: '訊息' },
                ]}
              />

              <DataTable<LoanOffer>
                title="貸出委託"
                description="本地紀錄的 dry-run/live offer intent 與結果。"
                rows={data.offers}
                columns={offerColumns}
              />

              <DataTable<LoanOffer>
                title="交易所未成交委託"
                description="由 sync-open-offers 取得的 read-only snapshot。"
                rows={data.openOffers}
                columns={openOfferColumns}
              />

              <DataTable<ActiveLoan>
                title="目前放貸中"
                description="交易所 active loans snapshot。"
                rows={data.activeLoans}
                columns={activeLoanColumns}
              />

              <DataTable<EarningsSummary>
                title="收益摘要"
                description="依幣種彙總今日、昨日與累積收益。"
                rows={data.earnings}
                columns={earningsColumns}
              />

              <DataTable<LendingHistoryEntry>
                title="收益明細"
                description="最近同步的 lending history。"
                rows={data.lendingHistory}
                columns={historyColumns}
              />

              <DataTable<MarketRate>
                title="市場利率"
                description="最近記錄的 lendbook rate snapshot。"
                rows={data.marketRates}
                columns={marketRateColumns}
              />

              <DataTable<MarketAnalysisRate>
                title="市場分析紀錄"
                description="由 record-market-analysis 記錄的 lendbook depth levels。"
                rows={data.marketAnalysisRates}
                columns={marketAnalysisColumns}
              />
            </section>
          ) : null}
        </>
      ) : null}
      {data && activePage !== 'overview' ? <PagePlaceholder page={activePage} /> : null}
          </div>
        </div>
      </main>
    </>
  )
}

type PageKey =
  | 'overview'
  | 'currencies'
  | 'earnings'
  | 'market'
  | 'offers'
  | 'actions'
  | 'settings'
  | 'logs'

const pageItems: Array<{ key: PageKey; label: string; description: string }> = [
  { key: 'overview', label: '總覽', description: '核心狀態與常用操作' },
  { key: 'currencies', label: '幣種狀態', description: '餘額、放貸中與幣種摘要' },
  { key: 'earnings', label: '收益與歷史', description: '收益圖表與 lending history' },
  { key: 'market', label: '市場分析', description: '利率紀錄與建議門檻' },
  { key: 'offers', label: '委託管理', description: '本地與交易所委託' },
  { key: 'actions', label: '安全操作', description: '同步、轉移、取消與 run once' },
  { key: 'settings', label: 'Bot 設定', description: 'SQLite managed settings' },
  { key: 'logs', label: '執行紀錄', description: 'Bot runs 與操作結果' },
]

function SidebarNavigation({
  activePage,
  onChange,
}: {
  activePage: PageKey
  onChange: (page: PageKey) => void
}) {
  return (
    <aside className="app-sidebar" aria-label="主要頁面">
      <div className="sidebar-heading">
        <span>Auto Lending Bot</span>
        <strong>控制台</strong>
      </div>
      <nav className="sidebar-nav">
        {pageItems.map((item) => (
          <button
            type="button"
            key={item.key}
            className={item.key === activePage ? 'active' : ''}
            onClick={() => onChange(item.key)}
          >
            <strong>{item.label}</strong>
            <span>{item.description}</span>
          </button>
        ))}
      </nav>
    </aside>
  )
}

function PagePlaceholder({ page }: { page: PageKey }) {
  const item = pageItems.find((entry) => entry.key === page)

  return (
    <section className="page-placeholder">
      <p className="eyebrow">Coming Next</p>
      <h2>{item?.label}</h2>
      <p>{item?.description} 會在下一個 phase 開始從總覽頁拆出來。</p>
    </section>
  )
}

function pageTitle(activePage: PageKey, fallbackLabel?: string): string {
  if (activePage === 'overview') {
    return fallbackLabel ?? 'Auto Lending Bot'
  }

  return pageItems.find((item) => item.key === activePage)?.label ?? 'Auto Lending Bot'
}

function pageDescription(activePage: PageKey): string {
  if (activePage === 'overview') {
    return '狀態、幣種明細、Log 與安全操作集中在同一個監控版面。'
  }

  return pageItems.find((item) => item.key === activePage)?.description ?? ''
}

const primaryActions: SafeActionName[] = [
  'run-once',
  'sync-open-offers',
  'record-market-analysis',
  'cancel-open-offers',
]

const displaySettingsKey = 'auto-lending-bot.displaySettings'
const adminTokenKey = 'auto-lending-bot.adminToken'
const defaultDisplaySettings: DisplaySettings = {
  compactLayout: false,
  showRawTables: true,
  btcUnit: 'BTC',
}

function loadDisplaySettings(): DisplaySettings {
  const saved = localStorage.getItem(displaySettingsKey)
  if (!saved) {
    return defaultDisplaySettings
  }

  try {
    return { ...defaultDisplaySettings, ...JSON.parse(saved) }
  } catch {
    return defaultDisplaySettings
  }
}

function loadAdminToken(): string {
  return sessionStorage.getItem(adminTokenKey) ?? ''
}

function ErrorState({ message }: { message: string }) {
  return (
    <section className="error-state">
      <strong>無法讀取 API</strong>
      <span>{message}</span>
    </section>
  )
}

function shouldConfirmLive(action: SafeActionName, dryRun: boolean) {
  return ['run-once', 'cancel-open-offers', 'transfer-funds'].includes(action) && !dryRun
}

const rate = (value: unknown) => (typeof value === 'number' ? `${(value * 100).toFixed(4)}%` : '-')
const amount = (value: unknown) => (typeof value === 'number' ? value.toPrecision(8) : '-')

const offerColumns = [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'amount', label: '數量', format: amount },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'duration_days', label: '天數' },
  { key: 'status', label: '狀態' },
  { key: 'external_offer_id', label: '交易所編號' },
] satisfies Parameters<typeof DataTable<LoanOffer>>[0]['columns']

const openOfferColumns = [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'amount', label: '數量', format: amount },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'duration_days', label: '天數' },
  { key: 'external_offer_id', label: '交易所編號' },
  { key: 'captured_at', label: '擷取時間' },
] satisfies Parameters<typeof DataTable<LoanOffer>>[0]['columns']

const activeLoanColumns = [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'amount', label: '數量', format: amount },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'duration_days', label: '天數' },
  { key: 'external_loan_id', label: '交易所編號' },
  { key: 'captured_at', label: '擷取時間' },
] satisfies Parameters<typeof DataTable<ActiveLoan>>[0]['columns']

const earningsColumns = [
  { key: 'currency', label: '幣種' },
  { key: 'today_earned', label: '今日收益', format: amount },
  { key: 'yesterday_earned', label: '昨日收益', format: amount },
  { key: 'total_earned', label: '累積收益', format: amount },
] satisfies Parameters<typeof DataTable<EarningsSummary>>[0]['columns']

const historyColumns = [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'interest', label: '利息', format: amount },
  { key: 'fee', label: '手續費', format: amount },
  { key: 'earned', label: '實收', format: amount },
  { key: 'closed_at', label: '結束時間' },
] satisfies Parameters<typeof DataTable<LendingHistoryEntry>>[0]['columns']

const marketRateColumns = [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'available_amount', label: '可用數量', format: amount },
  { key: 'captured_at', label: '擷取時間' },
] satisfies Parameters<typeof DataTable<MarketRate>>[0]['columns']

const marketAnalysisColumns = [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'level', label: 'Level' },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'available_amount', label: '可用數量', format: amount },
  { key: 'captured_at', label: '擷取時間' },
] satisfies Parameters<typeof DataTable<MarketAnalysisRate>>[0]['columns']
