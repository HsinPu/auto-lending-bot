import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

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
  BotRun,
  LendingHistoryEntry,
  LoanOffer,
  MarketAnalysisRate,
  MarketRate,
  SafeActionName,
  SafeActionResponse,
} from '../types/api'
import { formatTimestamp } from '../utils/time'

export function DashboardPage() {
  const queryClient = useQueryClient()
  const [latestResult, setLatestResult] = useState<SafeActionResponse | null>(null)
  const [latestError, setLatestError] = useState<string | null>(null)
  const [displaySettings, setDisplaySettings] = useState<DisplaySettings>(loadDisplaySettings)
  const [adminToken, setAdminToken] = useState(loadAdminToken)
  const [activePage, setActivePage] = useState<PageKey>(loadActivePage)
  const { data, error, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboardData,
  })
  const displayTimeZone = data?.settings.display_timezone ?? 'UTC'
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
  useEffect(() => {
    const syncPageFromHash = () => setActivePage(loadActivePage())
    window.addEventListener('hashchange', syncPageFromHash)
    return () => window.removeEventListener('hashchange', syncPageFromHash)
  }, [])
  const changePage = (page: PageKey) => {
    setActivePage(page)
    const nextHash = `#${page}`
    if (window.location.hash !== nextHash) {
      window.history.pushState(null, '', nextHash)
    }
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
          <SidebarNavigation activePage={activePage} adminToken={adminToken} onChange={changePage} />

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

          <div className="overview-layout">
            <div className="overview-main">
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

              <ActivityLog
                runs={data.runs}
                offers={data.offers}
                latestResult={latestResult}
                latestError={latestError}
                timeZone={displayTimeZone}
              />
            </div>

            <aside className="overview-side" aria-label="Overview details">
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
            </aside>
          </div>
        </>
      ) : null}
      {data && activePage === 'currencies' ? (
        <div className="page-stack">
          <CurrencyOverview details={data.currencyDetails} />
          <EarningsForecast details={data.currencyDetails} />
        </div>
      ) : null}
      {data && activePage === 'earnings' ? (
        <div className="page-stack">
          <ConvertedEarningsPanel rows={data.convertedEarnings} btcUnit={displaySettings.btcUnit} />
          <ProfitCharts history={data.lendingHistory} timeZone={displayTimeZone} />
          <DataTable<LendingHistoryEntry>
            title="收益明細"
            description="最近同步的 lending history。"
            rows={data.lendingHistory}
            columns={historyColumns(displayTimeZone)}
          />
        </div>
      ) : null}
      {data && activePage === 'market' ? (
        <div className="page-stack">
          <PageActionStrip
            title="市場分析操作"
            description="記錄 lendbook 深度後，後端會更新 suggested / effective min daily rate。"
            actionNames={['record-market-analysis']}
            isPending={actionMutation.isPending}
            onRunAction={(action) => runAction(action, data.status.dry_run)}
          />
          <MiniCharts earnings={data.earnings} marketRates={data.marketRates} offers={data.offers} />
          <section className="settings-panel">
            <div>
              <h2>利率門檻</h2>
              <p>{data.settings.smoke_test_currency} 的市場分析建議與實際策略門檻。</p>
            </div>
            <dl>
              <div>
                <dt>suggested min daily rate</dt>
                <dd>{rate(data.settings.market_analysis_suggested_min_daily_rate)}</dd>
              </div>
              <div>
                <dt>effective min daily rate</dt>
                <dd>{rate(data.settings.effective_min_daily_rate)}</dd>
              </div>
              <div>
                <dt>market analysis levels</dt>
                <dd>{data.settings.market_analysis_levels}</dd>
              </div>
            </dl>
          </section>
          <DataTable<MarketRate>
            title="市場利率"
            description="最近記錄的 lendbook rate snapshot。"
            rows={data.marketRates}
            columns={marketRateColumns(displayTimeZone)}
          />
          <DataTable<MarketAnalysisRate>
            title="市場分析紀錄"
            description="由 record-market-analysis 記錄的 lendbook depth levels。"
            rows={data.marketAnalysisRates}
            columns={marketAnalysisColumns(displayTimeZone)}
          />
        </div>
      ) : null}
      {data && activePage === 'offers' ? (
        <div className="page-stack">
          <PageActionStrip
            title="委託操作"
            description="同步交易所未成交委託；取消委託會遵守後端 dry-run / live guard。"
            actionNames={['sync-open-offers', 'cancel-open-offers']}
            isPending={actionMutation.isPending}
            onRunAction={(action) => runAction(action, data.status.dry_run)}
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
            columns={openOfferColumns(displayTimeZone)}
          />
        </div>
      ) : null}
      {data && activePage === 'actions' ? (
        <div className="page-stack">
          <section className="safety-action-header">
            <div>
              <p className="eyebrow">Protected Operations</p>
              <h2>安全操作中心</h2>
              <p>
                Live 模式操作需要 Admin Token 與後端 confirm guard。Dry-run 模式仍可用來驗證流程。
              </p>
            </div>
            <label className="admin-token-field">
              <span>Admin Token</span>
              <input
                type="password"
                value={adminToken}
                placeholder="ADMIN_AUTH_TOKEN"
                onChange={(event) => {
                  setAdminToken(event.currentTarget.value)
                  sessionStorage.setItem(adminTokenKey, event.currentTarget.value)
                }}
              />
            </label>
          </section>
          {!data.status.dry_run ? (
            <section className="live-warning-panel">
              <strong>Live 模式警示</strong>
              <p>Transfer funds、Cancel open offers、Run once 可能執行真實交易所操作。</p>
            </section>
          ) : null}
          <ActionPanel
            dryRun={data.status.dry_run}
            isPending={actionMutation.isPending}
            latestResult={latestResult}
            latestError={latestError}
            onRunAction={(action: SafeActionName) => runAction(action, data.status.dry_run)}
          />
        </div>
      ) : null}
      {data && activePage === 'settings' ? (
        <ManagedSettingsPanel
          adminToken={adminToken}
          onAdminTokenChange={(token) => {
            setAdminToken(token)
            sessionStorage.setItem(adminTokenKey, token)
          }}
        />
      ) : null}
      {data && activePage === 'logs' ? (
        <div className="page-stack">
          <ActivityLog
            runs={data.runs}
            offers={data.offers}
            latestResult={latestResult}
            latestError={latestError}
            timeZone={displayTimeZone}
          />
          <DataTable<BotRun>
            title="最近執行"
            description="Bot run 狀態與訊息。"
            rows={data.runs}
            columns={runColumns(displayTimeZone)}
          />
          <DataTable<LoanOffer>
            title="最近貸出活動"
            description="本地紀錄的 offer intent、dry-run 或 live 結果。"
            rows={data.offers}
            columns={offerColumns}
          />
        </div>
      ) : null}
      {data && !['overview', 'currencies', 'earnings', 'market', 'offers', 'actions', 'settings', 'logs'].includes(activePage) ? (
        <PagePlaceholder page={activePage} />
      ) : null}
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
  adminToken,
  onChange,
}: {
  activePage: PageKey
  adminToken: string
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
            aria-current={item.key === activePage ? 'page' : undefined}
            onClick={() => onChange(item.key)}
          >
            <strong>{item.label}</strong>
            <span>{item.description}</span>
          </button>
        ))}
      </nav>
      <div className={`sidebar-admin-state ${adminToken ? 'enabled' : ''}`}>
        <strong>{adminToken ? '管理權限已啟用' : '管理權限未啟用'}</strong>
        <span>{adminToken ? 'Live actions / settings writes 可送出 token' : '安全操作與設定寫入需要 Admin Token'}</span>
      </div>
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

function PageActionStrip({
  title,
  description,
  actionNames,
  isPending,
  onRunAction,
}: {
  title: string
  description: string
  actionNames: SafeActionName[]
  isPending: boolean
  onRunAction: (action: SafeActionName) => void
}) {
  return (
    <section className="quick-actions">
      <div>
        <p className="eyebrow">Page Controls</p>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      <div className="quick-action-buttons">
        {actionNames.map((actionName) => {
          const item = actions.find((entry) => entry.action === actionName)
          if (!item) {
            return null
          }

          return (
            <button
              type="button"
              className="quick-action-button"
              disabled={isPending}
              onClick={() => onRunAction(item.action)}
              key={item.action}
            >
              {isPending ? '執行中...' : item.label}
            </button>
          )
        })}
      </div>
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

function loadActivePage(): PageKey {
  const hashValue = window.location.hash.replace(/^#/, '')
  return isPageKey(hashValue) ? hashValue : 'overview'
}

function isPageKey(value: string): value is PageKey {
  return pageItems.some((item) => item.key === value)
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

const historyColumns = (timeZone: string) => [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'interest', label: '利息', format: amount },
  { key: 'fee', label: '手續費', format: amount },
  { key: 'earned', label: '實收', format: amount },
  { key: 'closed_at', label: '結束時間', format: (value: unknown) => formatTimestamp(value, timeZone) },
] satisfies Parameters<typeof DataTable<LendingHistoryEntry>>[0]['columns']

const runColumns = (timeZone: string) => [
  { key: 'id', label: '編號' },
  { key: 'status', label: '狀態' },
  { key: 'dry_run', label: '模擬' },
  { key: 'started_at', label: '開始時間', format: (value: unknown) => formatTimestamp(value, timeZone) },
  { key: 'finished_at', label: '結束時間', format: (value: unknown) => formatTimestamp(value, timeZone) },
  { key: 'message', label: '訊息' },
] satisfies Parameters<typeof DataTable<BotRun>>[0]['columns']

const offerColumns = [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'amount', label: '數量', format: amount },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'duration_days', label: '天數' },
  { key: 'status', label: '狀態' },
  { key: 'external_offer_id', label: '交易所編號' },
] satisfies Parameters<typeof DataTable<LoanOffer>>[0]['columns']

const openOfferColumns = (timeZone: string) => [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'amount', label: '數量', format: amount },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'duration_days', label: '天數' },
  { key: 'external_offer_id', label: '交易所編號' },
  { key: 'captured_at', label: '擷取時間', format: (value: unknown) => formatTimestamp(value, timeZone) },
] satisfies Parameters<typeof DataTable<LoanOffer>>[0]['columns']

const marketRateColumns = (timeZone: string) => [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'available_amount', label: '可用數量', format: amount },
  { key: 'captured_at', label: '擷取時間', format: (value: unknown) => formatTimestamp(value, timeZone) },
] satisfies Parameters<typeof DataTable<MarketRate>>[0]['columns']

const marketAnalysisColumns = (timeZone: string) => [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'level', label: 'Level' },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'available_amount', label: '可用數量', format: amount },
  { key: 'captured_at', label: '擷取時間', format: (value: unknown) => formatTimestamp(value, timeZone) },
] satisfies Parameters<typeof DataTable<MarketAnalysisRate>>[0]['columns']
