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
  LiveReadiness,
  LiveReadinessSection,
  LoanOffer,
  MarketAnalysisRate,
  MarketAnalysisStatus,
  MarketRate,
  SafeActionName,
  SafeActionResponse,
  StrategyDecision,
} from '../types/api'
import { formatAmount, formatRate } from '../utils/number'
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
                <p className="eyebrow">放貸控制台</p>
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
                <p className="eyebrow">Bot 控制</p>
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
                <StatusCard label="執行次數" value={data.status.counts.bot_runs} />
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
                    {data.settings.smoke_test_currency} | 策略除錯：
                    {data.settings.strategy_debug ? '開啟' : '關閉'}
                  </p>
                </div>
                <dl>
                  <div>
                    <dt>市場分析建議最低日利率</dt>
                    <dd>{rate(data.settings.market_analysis_suggested_min_daily_rate)}</dd>
                  </div>
                  <div>
                    <dt>有效最低日利率</dt>
                    <dd>{rate(data.settings.effective_min_daily_rate)}</dd>
                  </div>
                </dl>
                <dl>
                  {Object.entries(data.settings.strategy).map(([key, value]) => (
                    <div key={key}>
                      <dt>{strategyLabel(key)}</dt>
                      <dd>{formatStrategyValue(key, value)}</dd>
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
          <DataTable<StrategyDecision>
            title="策略決策表"
            description="每個幣別目前套用的策略、利率門檻與預計建立的委託。"
            rows={data.strategyDecisions}
            columns={strategyDecisionColumns}
          />
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
            description="記錄放貸簿深度後，後端會更新建議與有效最低日利率。"
            actionNames={['record-market-analysis']}
            isPending={actionMutation.isPending}
            onRunAction={(action) => runAction(action, data.status.dry_run)}
          />
          <MiniCharts earnings={data.earnings} marketRates={data.marketRates} offers={data.offers} />
          <DataTable<MarketAnalysisStatus>
            title="市場分析狀態"
            description="每個幣別的樣本數、資料新鮮度與建議利率狀態。"
            rows={data.marketAnalysisStatus}
            columns={marketAnalysisStatusColumns(displayTimeZone)}
          />
          <section className="settings-panel">
            <div>
              <h2>利率門檻</h2>
              <p>{data.settings.smoke_test_currency} 的市場分析建議與實際策略門檻。</p>
            </div>
            <dl>
              <div>
                  <dt>建議最低日利率</dt>
                <dd>{rate(data.settings.market_analysis_suggested_min_daily_rate)}</dd>
              </div>
              <div>
                  <dt>有效最低日利率</dt>
                <dd>{rate(data.settings.effective_min_daily_rate)}</dd>
              </div>
              <div>
                  <dt>市場分析深度層數</dt>
                <dd>{data.settings.market_analysis_levels}</dd>
              </div>
            </dl>
          </section>
          <DataTable<MarketRate>
            title="市場利率"
            description="最近記錄的放貸簿利率快照。"
            rows={data.marketRates}
            columns={marketRateColumns(displayTimeZone)}
          />
          <DataTable<MarketAnalysisRate>
            title="市場分析紀錄"
            description="由市場分析操作記錄的放貸簿深度資料。"
            rows={data.marketAnalysisRates}
            columns={marketAnalysisColumns(displayTimeZone)}
          />
        </div>
      ) : null}
      {data && activePage === 'offers' ? (
        <div className="page-stack">
          <PageActionStrip
            title="委託操作"
            description="同步交易所未成交委託；取消委託會遵守後端模擬模式與真實操作安全檢查。"
            actionNames={['sync-open-offers', 'cancel-open-offers']}
            isPending={actionMutation.isPending}
            onRunAction={(action) => runAction(action, data.status.dry_run)}
          />
          <DataTable<LoanOffer>
            title="貸出委託"
            description="本地紀錄的模擬或 Live 委託意圖與結果。"
            rows={data.offers}
            columns={offerColumns}
          />
          <DataTable<LoanOffer>
            title="交易所未成交委託"
            description="由同步委託取得的唯讀快照。"
            rows={data.openOffers}
            columns={openOfferColumns(displayTimeZone)}
          />
        </div>
      ) : null}
      {data && activePage === 'actions' ? (
        <div className="page-stack">
          <section className="safety-action-header">
            <div>
              <p className="eyebrow">受保護操作</p>
              <h2>安全操作中心</h2>
              <p>
                Live 模式操作需要管理權杖與後端二次確認。模擬模式仍可用來驗證流程。
              </p>
            </div>
            <label className="admin-token-field">
              <span>管理權杖</span>
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
              <p>執行轉帳、取消委託、執行一次可能會送出真實交易所操作。</p>
            </section>
          ) : null}
          <LiveReadinessPanel readiness={data.liveReadiness} />
          <ActionPanel
            dryRun={data.status.dry_run}
            botLoop={data.status.bot_loop}
            timeZone={displayTimeZone}
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
            description="Bot 執行狀態與訊息。"
            rows={data.runs}
            columns={runColumns(displayTimeZone)}
          />
          <DataTable<LoanOffer>
            title="最近貸出活動"
            description="本地紀錄的委託意圖、模擬或 Live 結果。"
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
  { key: 'earnings', label: '收益與歷史', description: '收益圖表與放貸歷史' },
  { key: 'market', label: '市場分析', description: '利率紀錄與建議門檻' },
  { key: 'offers', label: '委託管理', description: '本地與交易所委託' },
  { key: 'actions', label: '安全操作', description: '同步、轉移、取消與 run once' },
  { key: 'settings', label: 'Bot 設定', description: 'SQLite 設定覆寫' },
  { key: 'logs', label: '執行紀錄', description: 'Bot 執行與操作結果' },
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
        <span>{adminToken ? '外部連線可送出權杖' : '本機可直接寫入，外部連線需要權杖'}</span>
      </div>
    </aside>
  )
}

function PagePlaceholder({ page }: { page: PageKey }) {
  const item = pageItems.find((entry) => entry.key === page)

  return (
    <section className="page-placeholder">
        <p className="eyebrow">即將開放</p>
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
        <p className="eyebrow">頁面操作</p>
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

function LiveReadinessPanel({ readiness }: { readiness: LiveReadiness }) {
  return (
    <section className="settings-panel">
      <div>
        <p className="eyebrow">Live 就緒檢查</p>
        <h2>Live 設定檢查清單</h2>
        <p>{readinessNote(readiness.note)}</p>
      </div>
      <div className="settings-grid two-column">
        <LiveReadinessSectionView title="Live 放貸" section={readiness.live_offers} />
        <LiveReadinessSectionView title="Live 轉帳" section={readiness.live_transfers} />
      </div>
    </section>
  )
}

function LiveReadinessSectionView({
  title,
  section,
}: {
  title: string
  section: LiveReadinessSection
}) {
  return (
    <div className={`readiness-card ${section.ready ? 'ready' : 'blocked'}`}>
      <strong>{title}: {section.ready ? '已就緒' : '尚未就緒'}</strong>
      <ul>
        {section.items.map((item) => (
          <li key={item.label} className={item.ok ? 'ok' : 'missing'}>
            {item.ok ? '通過' : '缺少'}：{readinessLabel(item.label)}
          </li>
        ))}
      </ul>
    </div>
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
  'start-loop',
  'stop-loop',
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
  return ['run-once', 'start-loop', 'cancel-open-offers', 'transfer-funds'].includes(action) && !dryRun
}

const rate = (value: unknown) => formatRate(value)
const amount = (value: unknown) => formatAmount(value)
const yesNo = (value: unknown) => (value ? '是' : '否')

const percentageStrategyKeys = new Set([
  'min_daily_rate',
  'max_daily_rate',
  'xday_threshold',
  'frr_delta',
  'max_percent_to_lend',
  'max_to_lend_rate',
])

const strategyLabels: Record<string, string> = {
  min_daily_rate: '最低日利率',
  max_daily_rate: '最高日利率',
  min_loan_size: '最低放貸金額',
  spread_lend: '委託拆單數',
  gap_mode: 'Gap 模式',
  gap_bottom: 'Gap 下緣深度',
  gap_top: 'Gap 上緣深度',
  xday_threshold: '長天期利率門檻',
  xdays: '長天期天數',
  xday_spread: '長天期線性區間',
  frr_as_min: '使用 FRR 作為最低利率',
  frr_delta: 'FRR 調整值',
  max_percent_to_lend: '最大放貸百分比',
  max_amount_to_lend: '最大可放貸金額',
  max_active_amount: '最大放貸中金額',
  max_to_lend_rate: 'Max-to-lend 啟用利率',
  end_date: '停止放貸日期',
  hide_coins: '低於最低利率時保留資金',
}

const readinessLabels: Record<string, string> = {
  'EXCHANGE=bitfinex': '交易所設定為 Bitfinex',
  'BOT_DRY_RUN=false': '模擬模式關閉',
  'ALLOW_LIVE_TRADING=true': '允許 Live 交易',
  'ALLOW_BALANCE_TRANSFERS=true': '允許資金轉移',
  'BITFINEX_ENABLE_LIVE_OFFERS=true': '啟用 Bitfinex Live 放貸',
  'BITFINEX_ENABLE_LIVE_TRANSFERS=true': '啟用 Bitfinex Live 轉帳',
  'EXCHANGE_API_KEY is set': '已設定交易所 API Key',
  'EXCHANGE_API_SECRET is set': '已設定交易所 API Secret',
  'MAX_TOTAL_LEND_AMOUNT is set': '已設定單次執行總放貸上限',
  'MAX_SINGLE_OFFER_AMOUNT is set': '已設定單筆委託上限',
  'MAX_TOTAL_TRANSFER_AMOUNT is set': '已設定單次執行總轉帳上限',
  'MAX_SINGLE_TRANSFER_AMOUNT is set': '已設定單筆轉帳上限',
}

const reasonLabels: Record<string, string> = {
  'Created lending offers from available balance.': '已依可用餘額建立預計委託。',
  'No loan orders are available.': '目前沒有可參考的放貸簿委託。',
  'Available balance is below the minimum loan size.': '可用餘額低於最低放貸金額。',
  'Active lending amount is at or above the configured maximum.': '放貸中金額已達或超過設定上限。',
  'Best daily rate is below the configured minimum.': '最佳日利率低於設定的最低日利率。',
  'End date is too close to create new lending offers.': '停止放貸日期太近，不能建立新委託。',
  'Market analysis is disabled.': '市場分析已關閉。',
  'No market analysis samples have been recorded.': '尚未記錄市場分析樣本。',
  'Latest market analysis sample is older than the configured max age.': '最新市場分析資料已超過設定最大年齡。',
  'Not enough samples to calculate a suggestion.': '樣本數不足，無法計算建議利率。',
  'No suggested rate is available for the configured method.': '目前方法沒有可用的建議利率。',
  'Market analysis suggestion is available.': '市場分析建議利率可用。',
}

const statusLabels: Record<string, string> = {
  completed: '完成',
  failed: '失敗',
  running: '執行中',
  dry_run: '模擬',
  intent: '準備建立',
  created: '已建立',
  recorded: '已記錄',
}

function strategyLabel(key: string): string {
  return strategyLabels[key] ?? key
}

function readinessLabel(label: string): string {
  return readinessLabels[label] ?? label
}

function readinessNote(note: string): string {
  if (note === 'API keys should not include withdrawal permissions.') {
    return 'API key 不應包含提領權限。'
  }

  return note
}

function reasonLabel(value: unknown): string {
  if (typeof value !== 'string') {
    return '-'
  }

  return reasonLabels[value] ?? value
}

function statusLabel(value: unknown): string {
  if (typeof value !== 'string') {
    return '-'
  }

  return statusLabels[value] ?? value
}

function dryRunLabel(value: unknown): string {
  return value ? '是' : '否'
}

function formatStrategyValue(key: string, value: unknown): string {
  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }
  if (typeof value === 'number') {
    if (percentageStrategyKeys.has(key)) {
      return key === 'max_percent_to_lend' ? `${formatAmount(value)}%` : formatRate(value)
    }
    return formatAmount(value)
  }
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  return String(value)
}

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
  { key: 'status', label: '狀態', format: statusLabel },
  { key: 'dry_run', label: '模擬', format: dryRunLabel },
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
  { key: 'status', label: '狀態', format: statusLabel },
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
  { key: 'level', label: '層級' },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'available_amount', label: '可用數量', format: amount },
  { key: 'captured_at', label: '擷取時間', format: (value: unknown) => formatTimestamp(value, timeZone) },
] satisfies Parameters<typeof DataTable<MarketAnalysisRate>>[0]['columns']

const marketAnalysisStatusColumns = (timeZone: string) => [
  { key: 'currency', label: '幣種' },
  { key: 'method', label: '方法' },
  { key: 'sample_count', label: '樣本數' },
  { key: 'top_level_sample_count', label: '第一層樣本' },
  { key: 'min_samples', label: '最低樣本' },
  { key: 'max_age_seconds', label: '最大年齡秒數' },
  { key: 'latest_captured_at', label: '最新資料', format: (value: unknown) => formatTimestamp(value, timeZone) },
  { key: 'is_stale', label: '過期', format: yesNo },
  { key: 'has_enough_samples', label: '樣本足夠', format: yesNo },
  { key: 'suggested_min_daily_rate', label: '建議日利率', format: rate },
  { key: 'reason', label: '狀態原因', format: reasonLabel },
] satisfies Parameters<typeof DataTable<MarketAnalysisStatus>>[0]['columns']

const strategyDecisionColumns = [
  { key: 'currency', label: '幣種' },
  { key: 'balance', label: '可用餘額', format: amount },
  { key: 'active_amount', label: '放貸中', format: amount },
  { key: 'open_offer_amount', label: '未成交委託', format: amount },
  { key: 'best_market_rate', label: '最佳市場日利率', format: rate },
  { key: 'effective_min_daily_rate', label: '有效最低日利率', format: rate },
  { key: 'max_daily_rate', label: '最高日利率', format: rate },
  { key: 'max_to_lend', label: '最大可放貸', format: amount },
  { key: 'max_active_amount', label: '最大放貸中', format: amount },
  { key: 'offer_count', label: '預計委託數' },
  { key: 'offers', label: '預計委託', format: formatDecisionOffers },
  { key: 'reason', label: '原因', format: reasonLabel },
] satisfies Parameters<typeof DataTable<StrategyDecision>>[0]['columns']

function formatDecisionOffers(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) {
    return '-'
  }

  return value
    .map((offer) => {
      if (!offer || typeof offer !== 'object') {
        return ''
      }
      const item = offer as { amount?: number; daily_rate?: number; duration_days?: number }
      const offerAmount = typeof item.amount === 'number' ? formatAmount(item.amount) : '-'
      const offerRate = typeof item.daily_rate === 'number' ? formatRate(item.daily_rate) : '-'
      const days = typeof item.duration_days === 'number' ? item.duration_days : '-'
      return `${offerAmount} @ ${offerRate} / ${days} 天`
    })
    .filter(Boolean)
    .join('；')
}
