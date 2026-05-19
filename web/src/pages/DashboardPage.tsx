import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { cancelOpenOffer, getDashboardData, getRunDecisionHistory, runSafeAction, stopBotJob } from '../api/client'
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
import { TopStatusBar } from '../components/TopStatusBar'
import type {
  BotRun,
  BotRunStep,
  DashboardData,
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
  StrategyDecisionOffer,
  StrategyRateCandidate,
} from '../types/api'
import { formatAmount, formatRate } from '../utils/number'
import { formatTimestamp } from '../utils/time'

export function DashboardPage() {
  const queryClient = useQueryClient()
  const [latestResult, setLatestResult] = useState<SafeActionResponse | null>(null)
  const [latestError, setLatestError] = useState<string | null>(null)
  const [runOnceFlow, setRunOnceFlow] = useState<RunOnceFlowState | null>(null)
  const [pendingLiveAction, setPendingLiveAction] = useState<SafeActionName | null>(null)
  const [pendingCancelOffer, setPendingCancelOffer] = useState<LoanOffer | null>(null)
  const [pendingResetDryRun, setPendingResetDryRun] = useState(false)
  const [selectedHistoryRun, setSelectedHistoryRun] = useState<BotRun | null>(null)
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
    onSuccess: (result) => {
      setLatestResult(result)
      setLatestError(null)
      if (result.action === 'run-once') {
        setRunOnceFlow({ status: 'success', message: '執行一次完成，Dashboard 資料已重新整理。', result })
      }
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (mutationError, variables) => {
      setLatestResult(null)
      setLatestError((mutationError as Error).message)
      if (variables.action === 'run-once') {
        setRunOnceFlow({ status: 'error', message: (mutationError as Error).message })
      }
    },
  })
  const cancelOfferMutation = useMutation({
    mutationFn: ({ offer, confirmLive }: { offer: LoanOffer; confirmLive?: boolean }) => {
      if (!offer.external_offer_id) {
        throw new Error('這筆委託沒有交易所編號，無法取消。')
      }
      return cancelOpenOffer(offer.external_offer_id, { adminToken, confirmLive })
    },
    onSuccess: (result) => {
      setLatestResult(result)
      setLatestError(null)
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (mutationError) => {
      setLatestResult(null)
      setLatestError((mutationError as Error).message)
    },
  })
  const stopJobMutation = useMutation({
    mutationFn: (botJobId: number) => stopBotJob(botJobId),
    onSuccess: (result) => {
      setLatestResult(result)
      setLatestError(null)
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (mutationError) => {
      setLatestResult(null)
      setLatestError((mutationError as Error).message)
    },
  })
  const runAction = (action: SafeActionName, dryRun: boolean) => {
    if (action === 'reset-dry-run-records') {
      setPendingResetDryRun(true)
      return
    }

    const confirmLive = shouldConfirmLive(action, dryRun)
    if (confirmLive) {
      setPendingLiveAction(action)
      return
    }

    startAction(action, confirmLive, dryRun)
  }
  const startAction = (action: SafeActionName, confirmLive: boolean, dryRun: boolean) => {
    if (action === 'run-once') {
      setRunOnceFlow({ status: 'running', message: dryRun ? '模擬執行中，不會送出真實委託。' : 'Live 執行中，後端安全檢查會逐項阻擋不安全操作。' })
    }
    actionMutation.mutate({ action, confirmLive })
  }
  const cancelOffer = (offer: LoanOffer, dryRun: boolean) => {
    if (!dryRun) {
      setPendingCancelOffer(offer)
      return
    }
    cancelOfferMutation.mutate({ offer })
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
    window.scrollTo({ top: 0, behavior: 'smooth' })
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
        <div className="overview-page">
          <section className="overview-hero-panel" aria-label="Bot overview">
            <div>
              <p className="eyebrow">目前狀態</p>
              <h2>{data.status.dry_run ? '安全模擬執行中' : 'Live 模式啟用中'}</h2>
              <p>
                {data.status.exchange} 交易所 | {data.status.label} | 最近執行：
                {data.status.latest_run
                  ? formatTimestamp(data.status.latest_run.finished_at ?? data.status.latest_run.started_at, displayTimeZone)
                  : '尚無紀錄'}
              </p>
            </div>
            <div className={data.status.dry_run ? 'overview-mode-badge safe' : 'overview-mode-badge danger'}>
              <span>{data.status.dry_run ? 'DRY RUN' : 'LIVE'}</span>
              <strong>{data.status.dry_run ? '不會送出真實委託' : '會執行真實操作'}</strong>
            </div>
          </section>

          <section className="overview-metric-list" aria-label="Key metrics">
            <OverviewMetric label="執行次數" value={data.status.counts.bot_runs} />
            <OverviewMetric label="貸出委託" value={data.status.counts.loan_offers} />
            <OverviewMetric label="目前放貸中" value={data.status.counts.active_loans} />
            <OverviewMetric label="收益紀錄" value={data.status.counts.lending_history} />
            <OverviewMetric label="市場分析" value={data.status.counts.market_analysis_rates} />
            <OverviewMetric label="設定覆寫" value={data.status.settings_runtime.managed_override_count} />
          </section>

          <div className="overview-content-grid">
            <section className="overview-strategy-panel">
              <div className="section-heading compact">
                <div>
                  <h2>策略摘要</h2>
                  <p>
                    {data.settings.smoke_test_currency} | 策略除錯：
                    {data.settings.strategy_debug ? '開啟' : '關閉'}
                  </p>
                </div>
              </div>
              <dl className="overview-rate-summary">
                <div>
                  <dt>市場建議最低日利率</dt>
                  <dd>{rate(data.settings.market_analysis_suggested_min_daily_rate)}</dd>
                </div>
                <div>
                  <dt>有效最低日利率</dt>
                  <dd>{rate(data.settings.effective_min_daily_rate)}</dd>
                </div>
              </dl>
              <dl className="overview-strategy-list">
                {Object.entries(data.settings.strategy).map(([key, value]) => (
                  <div key={key}>
                    <dt>{strategyLabel(key)}</dt>
                    <dd>{formatStrategyValue(key, value)}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <ActivityLog
              runs={data.runs}
              offers={data.offers}
              latestResult={latestResult}
              latestError={latestError}
              timeZone={displayTimeZone}
            />
          </div>
        </div>
      ) : null}
      {data && activePage === 'currencies' ? (
        <div className="page-stack">
          <CurrencyOverview details={data.currencyDetails} />
          <StrategyDecisionPanel decisions={data.strategyDecisions} />
          <EarningsForecast details={data.currencyDetails} />
        </div>
      ) : null}
      {data && activePage === 'earnings' ? (
        <div className="earnings-page">
          <EarningsSummaryPanel history={data.lendingHistory} />
          <div className="earnings-content-grid">
            <ConvertedEarningsPanel rows={data.convertedEarnings} btcUnit={displaySettings.btcUnit} />
            <ProfitCharts history={data.lendingHistory} timeZone={displayTimeZone} />
          </div>
          <LendingHistoryList history={data.lendingHistory} timeZone={displayTimeZone} />
        </div>
      ) : null}
      {data && activePage === 'market' ? (
        <div className="market-page">
          <PageActionStrip
            title="市場分析操作"
            description="可手動記錄一次，也可以啟動背景收集，累積資料後用於百分位與 MACD 利率建議。"
            actionNames={['record-market-analysis', 'start-market-analysis', 'stop-market-analysis']}
            isPending={actionMutation.isPending}
            onRunAction={(action) => runAction(action, data.status.dry_run)}
          />
          <MarketSourcePanel data={data} />
          <div className="market-overview-grid">
            <MarketCollectionPanel data={data} timeZone={displayTimeZone} />
            <MarketThresholdPanel data={data} />
          </div>
          <MiniCharts earnings={data.earnings} marketRates={data.marketRates} offers={data.offers} />
          <MarketAnalysisStatusList rows={data.marketAnalysisStatus} timeZone={displayTimeZone} exchange={data.status.exchange} />
          <div className="market-data-grid">
            <MarketRateList rows={data.marketRates} timeZone={displayTimeZone} exchange={data.status.exchange} />
            <MarketDepthList rows={data.marketAnalysisRates} timeZone={displayTimeZone} exchange={data.status.exchange} />
          </div>
        </div>
      ) : null}
      {data && activePage === 'offers' ? (
        <div className="offers-page">
          <OffersSummaryPanel offers={data.offers} openOffers={data.openOffers} />
          <OfferListPanel
            title="貸出委託"
            description="本地紀錄的模擬或 Live 委託意圖與結果。"
            rows={data.offers}
            timeZone={displayTimeZone}
          />
          <OfferListPanel
            title="交易所未成交委託"
            description="由同步委託取得的快照；可針對單筆交易所委託送出取消。"
            rows={data.openOffers}
            timeZone={displayTimeZone}
            actionLabel="取消"
            actionPending={cancelOfferMutation.isPending}
            onCancelOffer={(offer) => cancelOffer(offer, data.status.dry_run)}
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
                Live 模式操作需要後台授權與後端二次確認。模擬模式仍可用來驗證流程。
              </p>
            </div>
            <label className="admin-token-field">
              <span>後台授權碼</span>
              <input
                type="password"
                value={adminToken}
                placeholder="遠端後台操作才需要"
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
            botJobs={data.jobs}
            timeZone={displayTimeZone}
            isPending={actionMutation.isPending || stopJobMutation.isPending}
            latestResult={latestResult}
            latestError={latestError}
            onRunAction={(action: SafeActionName) => runAction(action, data.status.dry_run)}
            onStopJob={(botJobId) => stopJobMutation.mutate(botJobId)}
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
          <RunHistoryTable
            runs={data.runs}
            timeZone={displayTimeZone}
            onViewDecisions={setSelectedHistoryRun}
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
      {runOnceFlow && data ? (
        <RunOnceFlowModal
          decisions={data.strategyDecisions}
          flow={runOnceFlow}
          onClose={() => setRunOnceFlow(null)}
        />
      ) : null}
      {selectedHistoryRun ? (
        <RunDecisionHistoryModal
          run={selectedHistoryRun}
          timeZone={displayTimeZone}
          onClose={() => setSelectedHistoryRun(null)}
        />
      ) : null}
      {pendingResetDryRun ? (
        <ResetDryRunConfirmModal
          onCancel={() => setPendingResetDryRun(false)}
          onConfirm={() => {
            setPendingResetDryRun(false)
            startAction('reset-dry-run-records', false, data?.status.dry_run ?? true)
          }}
        />
      ) : null}
      {pendingLiveAction && data ? (
        <LiveActionConfirmModal
          action={pendingLiveAction}
          onCancel={() => setPendingLiveAction(null)}
          onConfirm={() => {
            const action = pendingLiveAction
            setPendingLiveAction(null)
            startAction(action, true, data.status.dry_run)
          }}
        />
      ) : null}
      {pendingCancelOffer ? (
        <CancelOfferConfirmModal
          offer={pendingCancelOffer}
          onCancel={() => setPendingCancelOffer(null)}
          onConfirm={() => {
            const offer = pendingCancelOffer
            setPendingCancelOffer(null)
            cancelOfferMutation.mutate({ offer, confirmLive: true })
          }}
        />
      ) : null}
    </>
  )
}

type RunOnceFlowState = {
  status: 'running' | 'success' | 'error'
  message: string
  result?: SafeActionResponse
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
  { key: 'overview', label: '總覽', description: '先看 bot 是否正常' },
  { key: 'settings', label: 'Bot 設定', description: '設定交易所與安全模式' },
  { key: 'actions', label: '開始/停止放貸', description: '執行一次或開始持續執行' },
  { key: 'currencies', label: '幣種狀態', description: '看餘額與策略判斷' },
  { key: 'market', label: '市場分析', description: '看目前市場利率' },
  { key: 'offers', label: '委託管理', description: '查看已建立委託' },
  { key: 'earnings', label: '收益與歷史', description: '查看收益紀錄' },
  { key: 'logs', label: '執行紀錄', description: '檢查錯誤與執行結果' },
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
      <button
        type="button"
        className="sidebar-start-card"
        onClick={() => onChange('actions')}
      >
        <span>主要操作</span>
        <strong>開始放貸</strong>
        <small>到安全操作頁按「開始持續執行」，模擬模式不會送出真實委託。</small>
      </button>
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
        <strong>{adminToken ? '後台授權已啟用' : '後台授權未啟用'}</strong>
        <span>{adminToken ? '遠端後台操作會送出授權碼' : '本機可直接操作，遠端後台需要授權碼'}</span>
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

function RunHistoryTable({
  runs,
  timeZone,
  onViewDecisions,
}: {
  runs: BotRun[]
  timeZone: string
  onViewDecisions: (run: BotRun) => void
}) {
  const [page, setPage] = useState(1)
  const pageSize = 10
  const totalPages = Math.max(1, Math.ceil(runs.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const visibleRuns = runs.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  return (
    <section className="table-section">
      <div className="section-heading">
        <div>
          <h2>最近執行</h2>
          <p>Bot 執行狀態、訊息與逐幣別策略決策。</p>
        </div>
        <span>{runs.length} 筆</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>編號</th>
              <th>狀態</th>
              <th>模擬</th>
              <th>開始時間</th>
              <th>結束時間</th>
              <th>訊息</th>
              <th>決策</th>
            </tr>
          </thead>
          <tbody>
            {runs.length === 0 ? (
              <tr>
                <td colSpan={7}>目前沒有資料</td>
              </tr>
            ) : (
              visibleRuns.map((run) => (
                <tr key={run.id}>
                  <td>{run.id}</td>
                  <td>{statusLabel(run.status)}</td>
                  <td>{dryRunLabel(run.dry_run)}</td>
                  <td>{formatTimestamp(run.started_at, timeZone)}</td>
                  <td>{formatTimestamp(run.finished_at, timeZone)}</td>
                  <td>{run.message || '-'}</td>
                  <td>
                    <button type="button" className="table-inline-button" onClick={() => onViewDecisions(run)}>
                      查看決策
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {runs.length > 0 ? (
        <SimplePagination
          currentPage={currentPage}
          totalPages={totalPages}
          totalRows={runs.length}
          pageSize={pageSize}
          onPageChange={setPage}
        />
      ) : null}
    </section>
  )
}

function SimplePagination({
  currentPage,
  totalPages,
  totalRows,
  pageSize,
  onPageChange,
}: {
  currentPage: number
  totalPages: number
  totalRows: number
  pageSize: number
  onPageChange: (page: number) => void
}) {
  const start = (currentPage - 1) * pageSize + 1
  const end = Math.min(currentPage * pageSize, totalRows)

  return (
    <div className="pagination-controls">
      <span>
        顯示 {start}-{end} / {totalRows} 筆
      </span>
      <div>
        <button type="button" disabled={currentPage <= 1} onClick={() => onPageChange(currentPage - 1)}>
          上一頁
        </button>
        <strong>{currentPage} / {totalPages}</strong>
        <button type="button" disabled={currentPage >= totalPages} onClick={() => onPageChange(currentPage + 1)}>
          下一頁
        </button>
      </div>
    </div>
  )
}

function ResetDryRunConfirmModal({
  onCancel,
  onConfirm,
}: {
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="reset-dry-run-title">
      <section className="confirm-modal danger">
        <div className="modal-heading">
          <div>
            <p className="eyebrow">本地紀錄重置</p>
            <h2 id="reset-dry-run-title">重置所有模擬紀錄？</h2>
            <p>這只會刪除 SQLite 裡的 dry-run 紀錄，不會取消 Bitfinex 委託，也不會刪除 Live 紀錄。</p>
          </div>
        </div>
        <div className="confirm-detail-list">
          <strong>會刪除</strong>
          <ul>
            <li>dry-run 模擬委託</li>
            <li>dry-run bot runs</li>
            <li>dry-run 的逐幣別決策與執行步驟</li>
            <li>模擬來源的收益紀錄</li>
          </ul>
          <strong>不會刪除</strong>
          <ul>
            <li>Live 委託與 Live run 紀錄</li>
            <li>真實收益歷史、active loans、open offers 快照</li>
            <li>市場利率與設定資料</li>
          </ul>
        </div>
        <div className="confirm-actions">
          <button type="button" className="secondary-button" onClick={onCancel}>取消</button>
          <button type="button" className="danger-button" onClick={onConfirm}>確認重置</button>
        </div>
      </section>
    </div>
  )
}

function RunOnceFlowModal({
  decisions,
  flow,
  onClose,
}: {
  decisions: StrategyDecision[]
  flow: RunOnceFlowState
  onClose: () => void
}) {
  const running = flow.status === 'running'
  const failed = flow.status === 'error'
  const runSummary = runOnceResultSummary(flow.result)
  const visibleDecisions = runOnceResultDecisions(flow.result) ?? decisions
  const visibleSteps = runOnceResultSteps(flow.result)
  const groupedSteps = runOnceStepGroups(visibleSteps)

  return (
    <div className="modal-backdrop run-flow-backdrop" role="dialog" aria-modal="true" aria-labelledby="run-flow-title">
      <section className={`run-flow-modal ${flow.status}`}>
        <div className="modal-heading">
          <div>
            <p className="eyebrow">執行一次流程</p>
            <h2 id="run-flow-title">{running ? 'Bot 正在跑一輪策略' : failed ? '執行失敗' : '執行完成'}</h2>
            <p>{flow.message}</p>
          </div>
          <button type="button" className="modal-close-button" onClick={onClose}>
            關閉
          </button>
        </div>
        <div className="run-flow-step-groups">
          {groupedSteps.map((group) => (
            <section className="run-flow-step-group" key={group.title}>
              <h3>
                {group.title}
                <span>{group.steps.length} 筆</span>
              </h3>
              <ol className="run-flow-steps">
                {group.steps.map((step, index) => (
                  <li key={step.key} className={stepStatusClass(step.status, flow.status)}>
                    <span>{stepMarker(step.status, flow.status, index)}</span>
                    <details className="run-flow-step-detail">
                      <summary>
                        <div>
                          <strong>{step.label}</strong>
                          <p>{step.summary}</p>
                        </div>
                      </summary>
                      <div className="run-flow-step-body">
                        <RunFlowStepDetail detail={step.detail} />
                      </div>
                    </details>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
        {flow.result ? (
          <section className="run-flow-result-panel">
            <h3>本輪執行結果</h3>
            <dl>
              <HistoryMetric label="執行編號" value={runSummary.botRunId} />
              <HistoryMetric label="模式" value={runSummary.dryRun ? '模擬模式' : 'Live 模式'} />
              <HistoryMetric label="建立委託數" value={runSummary.createdCount} />
              <HistoryMetric label="執行狀態" value={statusLabel(runSummary.status)} />
              <HistoryMetric label="開始時間" value={runSummary.startedAt} />
              <HistoryMetric label="結束時間" value={runSummary.finishedAt} />
              <HistoryMetric label="執行訊息" value={runSummary.message} />
            </dl>
          </section>
        ) : null}
        {visibleDecisions.length > 0 ? (
          <section className="run-flow-decision-panel">
            <h3>逐幣別策略決策</h3>
            <div className="run-flow-decision-list">
              {visibleDecisions.map((decision) => (
                <article key={decision.currency}>
                  <div>
                    <strong>{decision.currency}</strong>
                    <span>{decision.offer_count > 0 ? `預計 ${decision.offer_count} 筆委託` : '本輪不建立委託'}</span>
                  </div>
                  <dl>
                    <HistoryMetric label="可用餘額" value={amount(decision.balance)} />
                    <HistoryMetric label="放貸中" value={amount(decision.active_amount)} />
                    <HistoryMetric label="最佳市場日利率" value={rate(decision.best_market_rate)} />
                    <HistoryMetric label="有效最低日利率" value={rate(decision.effective_min_daily_rate)} />
                    <HistoryMetric label="原因" value={reasonLabel(decision.reason)} />
                  </dl>
                  <DecisionRateCandidateList candidates={decision.rate_candidates} />
                </article>
              ))}
            </div>
          </section>
        ) : null}
        <p className="run-flow-note">
          後端會在本輪完成後回傳實際步驟紀錄；逐幣別策略決策使用本次 run 的快照。
        </p>
      </section>
    </div>
  )
}

function RunDecisionHistoryModal({ run, timeZone, onClose }: { run: BotRun; timeZone: string; onClose: () => void }) {
  const { data, error, isLoading } = useQuery({
    queryKey: ['run-decision-history', run.id],
    queryFn: () => getRunDecisionHistory(run.id),
  })
  const steps = data?.steps.map(historyStepView) ?? []
  const groupedSteps = runOnceStepGroups(steps)

  return (
    <div className="modal-backdrop run-flow-backdrop" role="dialog" aria-modal="true" aria-labelledby="run-history-title">
      <section className="run-flow-modal">
        <div className="modal-heading">
          <div>
            <p className="eyebrow">決策歷史</p>
            <h2 id="run-history-title">執行 #{run.id} 的策略決策</h2>
            <p>查看這一輪實際記錄下來的流程、逐幣別判斷與預計委託。</p>
          </div>
          <button type="button" className="modal-close-button" onClick={onClose}>
            關閉
          </button>
        </div>
        <section className="run-flow-result-panel">
          <h3>本輪執行結果</h3>
          <dl>
            <HistoryMetric label="執行編號" value={String(run.id)} />
            <HistoryMetric label="模式" value={run.dry_run ? '模擬模式' : 'Live 模式'} />
            <HistoryMetric label="執行狀態" value={statusLabel(run.status)} />
            <HistoryMetric label="開始時間" value={formatTimestamp(run.started_at, timeZone)} />
            <HistoryMetric label="結束時間" value={formatTimestamp(run.finished_at, timeZone)} />
            <HistoryMetric label="執行訊息" value={run.message || '-'} />
          </dl>
        </section>
        {isLoading ? <p className="run-flow-note">正在載入決策歷史...</p> : null}
        {error ? <p className="run-flow-note error">載入失敗：{(error as Error).message}</p> : null}
        {groupedSteps.length > 0 ? (
          <div className="run-flow-step-groups">
            {groupedSteps.map((group) => (
              <section className="run-flow-step-group" key={group.title}>
                <h3>
                  {group.title}
                  <span>{group.steps.length} 筆</span>
                </h3>
                <ol className="run-flow-steps">
                  {group.steps.map((step, index) => (
                    <li key={step.key} className={stepStatusClass(step.status, 'success')}>
                      <span>{stepMarker(step.status, 'success', index)}</span>
                      <details className="run-flow-step-detail">
                        <summary>
                          <div>
                            <strong>{step.label}</strong>
                            <p>{step.summary}</p>
                          </div>
                        </summary>
                        <div className="run-flow-step-body">
                          <RunFlowStepDetail detail={step.detail} />
                        </div>
                      </details>
                    </li>
                  ))}
                </ol>
              </section>
            ))}
          </div>
        ) : null}
        {data?.decisions.length ? (
          <section className="run-flow-decision-panel">
            <h3>逐幣別策略決策</h3>
            <div className="run-flow-decision-list">
              {data.decisions.map((decision) => (
                <article key={decision.currency}>
                  <div>
                    <strong>{decision.currency}</strong>
                    <span>{decision.offer_count > 0 ? `預計 ${decision.offer_count} 筆委託` : '本輪不建立委託'}</span>
                  </div>
                  <dl>
                    <HistoryMetric label="可用餘額" value={amount(decision.balance)} />
                    <HistoryMetric label="放貸中" value={amount(decision.active_amount)} />
                    <HistoryMetric label="未成交委託" value={amount(decision.open_offer_amount)} />
                    <HistoryMetric label="最佳市場日利率" value={rate(decision.best_market_rate)} />
                    <HistoryMetric label="有效最低日利率" value={rate(decision.effective_min_daily_rate)} />
                    <HistoryMetric label="最佳市場年化" value={rate(decision.best_market_rate * 365)} />
                    <HistoryMetric label="有效最低年化" value={rate(decision.effective_min_daily_rate * 365)} />
                    <HistoryMetric label="原因" value={reasonLabel(decision.reason)} />
                  </dl>
                  <DecisionOfferList offers={decision.offers} offerCount={decision.offer_count} />
                  <DecisionRateCandidateList candidates={decision.rate_candidates} />
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {data && data.decisions.length === 0 ? <p className="run-flow-note">這一輪沒有記錄逐幣別決策。</p> : null}
      </section>
    </div>
  )
}

function historyStepView(step: BotRunStep): RunOnceStepView {
  return {
    key: String(step.id),
    stepKey: step.step_key,
    label: step.label,
    status: step.status,
    summary: runOnceStepSummary(step.step_key),
    detail: step.message || stepTimeRange(step),
  }
}

function DecisionOfferList({ offers, offerCount }: { offers: StrategyDecisionOffer[]; offerCount: number }) {
  if (offers.length === 0) {
    return <p className="decision-offer-empty">{offerCount > 0 ? `預計 ${offerCount} 筆委託` : '沒有預計委託'}</p>
  }

  return (
    <ul className="decision-offer-list">
      {offers.map((offer) => (
        <li key={`${offer.currency}-${offer.amount}-${offer.daily_rate}-${offer.duration_days}`}>
          <strong>{amount(offer.amount)}</strong>
          <span>日利率 {rate(offer.daily_rate)}</span>
          <span>年化 {rate(offer.daily_rate * 365)}</span>
          <span>{offer.duration_days} 天</span>
        </li>
      ))}
    </ul>
  )
}

function DecisionRateCandidateList({ candidates }: { candidates?: StrategyRateCandidate[] }) {
  if (!candidates?.length) {
    return <p className="decision-offer-empty">沒有候選利率資料</p>
  }

  return (
    <ul className="rate-candidate-list">
      {candidates.map((candidate) => (
        <li
          key={`${candidate.daily_rate}-${candidate.fill_probability}-${candidate.selection_role}`}
          className={candidate.selected ? 'selected' : undefined}
        >
          <strong>{rate(candidate.daily_rate * 365)} 年化</strong>
          <span>日利率 {rate(candidate.daily_rate)}</span>
          <span>成交率 {rate(candidate.fill_probability)}</span>
          <span>期望分數 {amount(candidate.expected_score)}</span>
          <span>{candidate.meets_min_probability ? '通過門檻' : '未達門檻'}</span>
          {candidate.selection_role ? <span>分層 {candidate.selection_role}</span> : null}
          {candidate.source ? <span>來源 {candidate.source}</span> : null}
        </li>
      ))}
    </ul>
  )
}

function LiveActionConfirmModal({
  action,
  onCancel,
  onConfirm,
}: {
  action: SafeActionName
  onCancel: () => void
  onConfirm: () => void
}) {
  const actionLabel = actions.find((item) => item.action === action)?.label ?? action

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="live-confirm-title">
      <section className="confirm-modal danger">
        <div className="modal-heading">
          <div>
            <p className="eyebrow">Live 操作確認</p>
            <h2 id="live-confirm-title">確認執行「{actionLabel}」？</h2>
            <p>Live 模式會執行真實交易所操作。後端仍會套用安全保險絲，但請確認金額上限與 API 權限後再繼續。</p>
          </div>
        </div>
        <div className="confirm-actions">
          <button type="button" className="secondary-button" onClick={onCancel}>取消</button>
          <button type="button" className="danger-button" onClick={onConfirm}>確認執行</button>
        </div>
      </section>
    </div>
  )
}

function RunFlowStepDetail({ detail }: { detail: string }) {
  const lines = detail.split('\n').map((line) => line.trim()).filter(Boolean)
  const settingDetail = runFlowSettingDetail(lines)
  if (settingDetail) {
    return (
      <div className="run-flow-setting-card">
        <strong>{settingDetail.title}</strong>
        <p>{settingDetail.impact}</p>
        <code>{settingDetail.setting}</code>
      </div>
    )
  }

  const heading = lines.length > 1 && !lines[0].startsWith('- ') ? lines[0] : null
  const listItems = lines.filter((line) => line.startsWith('- ')).map((line) => line.slice(2))

  if (listItems.length > 0) {
    return (
      <>
        {heading ? <p>{heading}</p> : null}
        <ul>
          {listItems.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </>
    )
  }

  if (lines.length > 1) {
    return (
      <div className="run-flow-detail-lines">
        {lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
    )
  }

  return <p>{detail}</p>
}

function runFlowSettingDetail(lines: string[]) {
  if (lines.length !== 3 || !lines[1].startsWith('影響：') || !lines[2].startsWith('設定鍵：')) {
    return null
  }

  return {
    title: lines[0],
    impact: lines[1].replace(/^影響：/, ''),
    setting: lines[2].replace(/^設定鍵：/, ''),
  }
}

function runOnceResultSummary(result: SafeActionResponse | undefined) {
  const latestRun = result?.latest_run as BotRun | undefined

  return {
    botRunId: String(result?.bot_run_id ?? latestRun?.id ?? '-'),
    createdCount: String(result?.created_count ?? 0),
    dryRun: Boolean(result?.dry_run),
    finishedAt: String(result?.finished_at ?? latestRun?.finished_at ?? '-'),
    message: String(result?.message ?? latestRun?.message ?? '-'),
    startedAt: String(result?.started_at ?? latestRun?.started_at ?? '-'),
    status: String(result?.status ?? latestRun?.status ?? '-'),
  }
}

function runOnceResultDecisions(result: SafeActionResponse | undefined): StrategyDecision[] | null {
  return Array.isArray(result?.decisions) ? (result.decisions as StrategyDecision[]) : null
}

function runOnceResultSteps(result: SafeActionResponse | undefined) {
  if (!Array.isArray(result?.steps)) {
    return runOnceFlowSteps.map((step) => ({
      key: step.key,
      stepKey: step.stepKey,
      label: step.label,
      status: step.status,
      summary: step.description,
      detail: '尚未收到後端執行紀錄。',
    }))
  }

  const steps = result.steps as BotRunStep[]
  return steps.map((step) => ({
    key: String(step.id),
    stepKey: step.step_key,
    label: step.label,
    status: step.status,
    summary: runOnceStepSummary(step.step_key),
    detail: step.message || stepTimeRange(step),
  }))
}

function runOnceStepSummary(stepKey: string) {
  return runOnceFlowSteps.find((step) => step.stepKey === stepKey)?.description ?? '後端回傳的實際執行步驟。'
}

function runOnceStepGroups(steps: RunOnceStepView[]) {
  return runOnceFlowGroups
    .map((group) => ({
      title: group.title,
      steps: steps.filter((step) => group.stepKeys.includes(step.stepKey)),
    }))
    .filter((group) => group.steps.length > 0)
}

function stepStatusClass(stepStatus: string | undefined, flowStatus: RunOnceFlowState['status']) {
  if (stepStatus === 'failed') {
    return 'error'
  }
  if (stepStatus === 'skipped') {
    return 'skipped'
  }
  if (stepStatus === 'pending') {
    return 'pending'
  }
  if (stepStatus === 'running') {
    return 'running'
  }
  return flowStatus === 'error' ? 'error' : 'success'
}

function stepMarker(stepStatus: string | undefined, flowStatus: RunOnceFlowState['status'], index: number) {
  if (stepStatus === 'failed' || flowStatus === 'error') {
    return '!'
  }
  if (stepStatus === 'skipped') {
    return '略'
  }
  if (stepStatus === 'pending') {
    return '待'
  }
  if (stepStatus === 'running' || flowStatus === 'running') {
    return index + 1
  }
  return '✓'
}

function stepTimeRange(step: BotRunStep) {
  const startedAt = step.started_at || '-'
  const finishedAt = step.finished_at || '-'
  return `${startedAt} -> ${finishedAt}`
}

type RunOnceStepView = {
  key: string
  stepKey: string
  label: string
  status: string
  summary: string
  detail: string
}

const runOnceFlowGroups = [
  {
    title: '執行準備',
    stepKeys: ['create-run'],
  },
  {
    title: '資料同步',
    stepKeys: [
      'read-previous-active-loans',
      'read-active-loans',
      'replace-active-loans',
      'detect-new-active-loans',
      'read-lending-balances',
      'check-open-offer-rebalance-setting',
      'sync-open-offers',
      'replace-open-offers',
      'check-open-offer-cancel-setting',
      'rebalance-open-offers',
      'evaluate-open-offer-cancel',
      'cancel-open-offer',
    ],
  },
  {
    title: '市場與策略',
    stepKeys: [
      'load-market-orders',
      'record-market-orders',
      'load-strategy-config',
      'load-frr-rate',
      'load-btc-price',
      'load-market-analysis-rate',
      'calculate-active-amount',
      'calculate-decisions',
      'record-decisions',
    ],
  },
  {
    title: '委託建立',
    stepKeys: [
      'prepare-offers',
      'record-dry-run-offer',
      'validate-live-offer',
      'record-live-intent',
      'submit-live-offer',
      'update-offer-result',
    ],
  },
  {
    title: '完成與通知',
    stepKeys: ['finish-run', 'send-run-summary', 'send-periodic-summary', 'send-xday-notification', 'send-error-notification'],
  },
]

const runOnceFlowSteps = [
  {
    key: 'create-run',
    stepKey: 'create-run',
    title: '建立本次執行紀錄',
    label: '建立本次執行紀錄',
    status: 'pending',
    description: '在 SQLite 建立這一輪 bot run，用來追蹤成功、失敗與執行訊息。',
  },
  {
    key: 'read-previous-active-loans',
    stepKey: 'read-previous-active-loans',
    title: '讀取本地舊放貸資料',
    label: '讀取本地舊放貸資料',
    status: 'pending',
    description: '讀取上一輪保存在 SQLite 的 active loans，用來比對新成交。',
  },
  {
    key: 'read-active-loans',
    stepKey: 'read-active-loans',
    title: '讀取交易所放貸中資料',
    label: '讀取交易所放貸中資料',
    status: 'pending',
    description: '從交易所讀取目前已成交、正在放貸中的資料。',
  },
  {
    key: 'replace-active-loans',
    stepKey: 'replace-active-loans',
    title: '更新本地放貸中資料',
    label: '更新本地放貸中資料',
    status: 'pending',
    description: '用交易所最新 active loans 取代本地快照。',
  },
  {
    key: 'detect-new-active-loans',
    stepKey: 'detect-new-active-loans',
    title: '檢查新成交放貸',
    label: '檢查新成交放貸',
    status: 'pending',
    description: '比對上一輪與這一輪的放貸中資料，必要時發送成交通知。',
  },
  {
    key: 'read-lending-balances',
    stepKey: 'read-lending-balances',
    title: '讀取可用 Lending 餘額',
    label: '讀取可用 Lending 餘額',
    status: 'pending',
    description: '確認 Funding/Lending wallet 裡哪些幣可以放貸。',
  },
  {
    key: 'check-open-offer-rebalance-setting',
    stepKey: 'check-open-offer-rebalance-setting',
    title: '檢查未成交委託同步設定',
    label: '檢查未成交委託同步設定',
    status: 'pending',
    description: '檢查是否啟用 open offer rebalance。',
  },
  {
    key: 'sync-open-offers',
    stepKey: 'sync-open-offers',
    title: '檢查未成交委託',
    label: '檢查未成交委託',
    status: 'pending',
    description: '視設定同步目前還掛在市場上的未成交委託。',
  },
  {
    key: 'replace-open-offers',
    stepKey: 'replace-open-offers',
    title: '更新本地未成交委託',
    label: '更新本地未成交委託',
    status: 'pending',
    description: '用交易所最新 open offers 更新本地快照。',
  },
  {
    key: 'check-open-offer-cancel-setting',
    stepKey: 'check-open-offer-cancel-setting',
    title: '檢查舊委託取消設定',
    label: '檢查舊委託取消設定',
    status: 'pending',
    description: '檢查目前是否允許取消舊委託。',
  },
  {
    key: 'rebalance-open-offers',
    stepKey: 'rebalance-open-offers',
    title: '處理舊委託',
    label: '處理舊委託',
    status: 'pending',
    description: '視設定決定是否保留或取消不符合策略的舊委託。',
  },
  {
    key: 'evaluate-open-offer-cancel',
    stepKey: 'evaluate-open-offer-cancel',
    title: '評估舊委託是否取消',
    label: '評估舊委託是否取消',
    status: 'pending',
    description: '逐筆判斷舊委託是否應該保留或取消。',
  },
  {
    key: 'cancel-open-offer',
    stepKey: 'cancel-open-offer',
    title: '取消舊委託',
    label: '取消舊委託',
    status: 'pending',
    description: '取消一筆不符合策略且允許取消的舊委託。',
  },
  {
    key: 'load-market-orders',
    stepKey: 'load-market-orders',
    title: '讀取市場利率',
    label: '讀取市場利率',
    status: 'pending',
    description: '逐幣別讀取 lending order book，確認目前市場利率。',
  },
  {
    key: 'record-market-orders',
    stepKey: 'record-market-orders',
    title: '記錄市場資料',
    label: '記錄市場資料',
    status: 'pending',
    description: '把本輪讀到的市場利率快照寫入 SQLite。',
  },
  {
    key: 'load-strategy-config',
    stepKey: 'load-strategy-config',
    title: '載入策略設定',
    label: '載入策略設定',
    status: 'pending',
    description: '載入該幣的策略設定與覆寫值。',
  },
  {
    key: 'load-frr-rate',
    stepKey: 'load-frr-rate',
    title: '讀取 FRR 利率',
    label: '讀取 FRR 利率',
    status: 'pending',
    description: '需要 FRR 作為最低利率時，讀取該幣 FRR。',
  },
  {
    key: 'load-btc-price',
    stepKey: 'load-btc-price',
    title: '讀取 BTC 參考價格',
    label: '讀取 BTC 參考價格',
    status: 'pending',
    description: '需要 BTC depth 換算時，讀取該幣 BTC 價格。',
  },
  {
    key: 'load-market-analysis-rate',
    stepKey: 'load-market-analysis-rate',
    title: '讀取市場分析建議利率',
    label: '讀取市場分析建議利率',
    status: 'pending',
    description: '從 SQLite 讀取市場分析建議最低日利率。',
  },
  {
    key: 'calculate-active-amount',
    stepKey: 'calculate-active-amount',
    title: '計算已放貸金額',
    label: '計算已放貸金額',
    status: 'pending',
    description: '計算該幣目前已成交、正在放貸中的金額。',
  },
  {
    key: 'calculate-decisions',
    stepKey: 'calculate-decisions',
    title: '計算策略決策',
    label: '計算策略決策',
    status: 'pending',
    description: '決定每個幣是否下單、下幾筆、金額與利率。',
  },
  {
    key: 'record-decisions',
    stepKey: 'record-decisions',
    title: '保存策略決策',
    label: '保存策略決策',
    status: 'pending',
    description: '保存本輪每個幣的策略決策快照，供 Dashboard 回看。',
  },
  {
    key: 'prepare-offers',
    stepKey: 'prepare-offers',
    title: '準備委託',
    label: '準備委託',
    status: 'pending',
    description: '依策略決策整理本輪要建立的 lending offers。',
  },
  {
    key: 'record-dry-run-offer',
    stepKey: 'record-dry-run-offer',
    title: '記錄模擬委託',
    label: '記錄模擬委託',
    status: 'pending',
    description: '模擬模式逐筆寫本地委託紀錄，不送出到交易所。',
  },
  {
    key: 'validate-live-offer',
    stepKey: 'validate-live-offer',
    title: 'Live 金額安全檢查',
    label: 'Live 金額安全檢查',
    status: 'pending',
    description: 'Live 模式下單前檢查單筆與本輪總額上限。',
  },
  {
    key: 'record-live-intent',
    stepKey: 'record-live-intent',
    title: '建立 Live 委託意圖',
    label: '建立 Live 委託意圖',
    status: 'pending',
    description: '真正送單前先寫入本地 intent，方便追蹤嘗試紀錄。',
  },
  {
    key: 'submit-live-offer',
    stepKey: 'submit-live-offer',
    title: '送出 Bitfinex 委託',
    label: '送出 Bitfinex 委託',
    status: 'pending',
    description: 'Live 模式呼叫交易所建立 lending offer。',
  },
  {
    key: 'update-offer-result',
    stepKey: 'update-offer-result',
    title: '更新委託結果',
    label: '更新委託結果',
    status: 'pending',
    description: '成功標記 created，失敗標記 failed 並保存錯誤訊息。',
  },
  {
    key: 'finish-run',
    stepKey: 'finish-run',
    title: '完成本次執行',
    label: '完成本次執行',
    status: 'pending',
    description: '寫入本輪 completed/failed 與摘要訊息。',
  },
  {
    key: 'send-run-summary',
    stepKey: 'send-run-summary',
    title: '發送本輪摘要通知',
    label: '發送本輪摘要通知',
    status: 'pending',
    description: '發送本輪建立委託數與 active loans 摘要。',
  },
  {
    key: 'send-periodic-summary',
    stepKey: 'send-periodic-summary',
    title: '發送週期摘要通知',
    label: '發送週期摘要通知',
    status: 'pending',
    description: '依通知間隔設定發送週期放貸摘要。',
  },
  {
    key: 'send-xday-notification',
    stepKey: 'send-xday-notification',
    title: '發送長天期委託通知',
    label: '發送長天期委託通知',
    status: 'pending',
    description: '當委託天期超過門檻且通知啟用時發送通知。',
  },
  {
    key: 'send-error-notification',
    stepKey: 'send-error-notification',
    title: '發送錯誤通知',
    label: '發送錯誤通知',
    status: 'pending',
    description: '執行失敗且錯誤通知啟用時發送通知。',
  },
]

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

function OverviewMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="overview-metric-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function EarningsSummaryPanel({ history }: { history: LendingHistoryEntry[] }) {
  const totalInterest = history.reduce((sum, row) => sum + row.interest, 0)
  const totalFee = history.reduce((sum, row) => sum + row.fee, 0)
  const totalEarned = history.reduce((sum, row) => sum + row.earned, 0)
  const currencies = new Set(history.map((row) => row.currency)).size
  const simulatedCount = history.filter((row) => row.dry_run).length
  const liveCount = history.length - simulatedCount

  return (
    <section className="earnings-summary-panel">
      <div>
        <p className="eyebrow">收益總覽</p>
        <h2>{amount(totalEarned)}</h2>
        <p>依目前同步的 lending history 彙整，扣除手續費後的累積實收。</p>
      </div>
      <div className="earnings-summary-metrics">
        <OverviewMetric label="收益筆數" value={history.length} />
        <OverviewMetric label="真實 / 模擬" value={`${liveCount} / ${simulatedCount}`} />
        <OverviewMetric label="涵蓋幣種" value={currencies} />
        <OverviewMetric label="利息合計" value={amount(totalInterest)} />
        <OverviewMetric label="手續費合計" value={amount(totalFee)} />
      </div>
    </section>
  )
}

function LendingHistoryList({
  history,
  timeZone,
}: {
  history: LendingHistoryEntry[]
  timeZone: string
}) {
  const [page, setPage] = useState(1)
  const pageSize = 10
  const totalPages = Math.max(1, Math.ceil(history.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const visibleRows = history.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  return (
    <section className="lending-history-panel">
      <div className="section-heading compact">
        <div>
          <h2>收益明細</h2>
          <p>最近同步的 lending history，每列顯示真實/模擬來源、利息、手續費與實收。</p>
        </div>
        <span>{history.length} 筆</span>
      </div>

      {history.length === 0 ? (
        <p className="empty-hint padded">目前沒有 lending history。</p>
      ) : (
        <>
          <div className="lending-history-table-scroll">
            <table className="lending-history-table">
              <thead>
                <tr>
                  <th>編號</th>
                  <th>模式</th>
                  <th>來源</th>
                  <th>幣種</th>
                  <th>利息</th>
                  <th>手續費</th>
                  <th>實收</th>
                  <th>本金</th>
                  <th>日利率</th>
                  <th>天數</th>
                  <th>結束時間</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.id}</td>
                    <td>{historyModeLabel(entry.dry_run)}</td>
                    <td>{entry.source}</td>
                    <td>{entry.currency}</td>
                    <td>{amount(entry.interest)}</td>
                    <td>{amount(entry.fee)}</td>
                    <td>{amount(entry.earned)}</td>
                    <td>{amount(entry.amount)}</td>
                    <td>{rate(entry.daily_rate)}</td>
                    <td>{entry.duration_days} 天</td>
                    <td>{formatTimestamp(entry.closed_at, timeZone)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PaginationControls
            currentPage={currentPage}
            totalPages={totalPages}
            totalRows={history.length}
            pageSize={pageSize}
            onPageChange={setPage}
          />
        </>
      )}
    </section>
  )
}

function HistoryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function MarketSourcePanel({ data }: { data: DashboardData }) {
  const sourceLabel = data.status.exchange === 'mock' ? 'Mock 模擬交易所' : data.status.exchange
  const modeLabel = data.status.dry_run ? '模擬模式，僅讀取/記錄資料' : 'Live 模式，請確認安全設定'

  return (
    <section className="market-source-panel">
      <div>
        <p className="eyebrow">資料來源</p>
        <h2>{sourceLabel}</h2>
        <p>
          市場分析資料由後端 exchange adapter 讀取 lendbook / funding book 後寫入 SQLite，前端只讀取本地 API
          顯示。
        </p>
      </div>
      <dl>
        <HistoryMetric label="目前交易所" value={data.status.exchange} />
        <HistoryMetric label="執行模式" value={modeLabel} />
        <HistoryMetric label="市場利率資料" value="market_rates：最近市場利率快照" />
        <HistoryMetric label="分析深度資料" value="market_analysis_rates：多層放貸簿深度紀錄" />
      </dl>
    </section>
  )
}

function MarketCollectionPanel({ data, timeZone }: { data: DashboardData; timeZone: string }) {
  const collection = data.status.market_analysis_collection
  return (
    <section className="market-panel market-collection-panel">
      <div>
        <p className="eyebrow">資料收集</p>
        <h2>{collection.running ? '收集中' : '未啟動'}</h2>
        <p>從 {data.status.exchange} 定期抓取設定幣別的放貸簿深度，寫入市場分析紀錄。</p>
      </div>
      <dl className="market-metric-list">
        <HistoryMetric label="完成輪數" value={String(collection.loops_completed)} />
        <HistoryMetric label="收集間隔" value={`${data.settings.market_analysis_interval_seconds} 秒`} />
        <HistoryMetric label="上次新增筆數" value={String(collection.last_changed_count)} />
        <HistoryMetric label="上次收集時間" value={formatTimestamp(collection.last_run_at, timeZone)} />
        {collection.last_error ? <HistoryMetric label="最近錯誤" value={collection.last_error} /> : null}
      </dl>
    </section>
  )
}

function MarketThresholdPanel({ data }: { data: DashboardData }) {
  return (
    <section className="market-panel">
      <div>
        <p className="eyebrow">利率門檻</p>
        <h2>{data.settings.smoke_test_currency}</h2>
        <p>市場分析建議與目前實際策略門檻。</p>
      </div>
      <dl className="market-metric-list compact">
        <HistoryMetric label="建議最低日利率" value={rate(data.settings.market_analysis_suggested_min_daily_rate)} />
        <HistoryMetric label="有效最低日利率" value={rate(data.settings.effective_min_daily_rate)} />
        <HistoryMetric label="市場分析深度層數" value={String(data.settings.market_analysis_levels)} />
      </dl>
    </section>
  )
}

function MarketAnalysisStatusList({
  rows,
  timeZone,
  exchange,
}: {
  rows: MarketAnalysisStatus[]
  timeZone: string
  exchange: string
}) {
  const [page, setPage] = useState(1)
  const pageSize = 10
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const visibleRows = rows.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  return (
    <section className="market-panel">
      <div className="section-heading compact">
        <div>
          <h2>市場分析狀態</h2>
          <p>依 {exchange} 已記錄樣本計算每個幣別的新鮮度、樣本數與建議利率。</p>
        </div>
        <span>{rows.length} 幣別</span>
      </div>
      {rows.length === 0 ? (
        <p className="empty-hint padded">目前沒有市場分析狀態。</p>
      ) : (
        <>
          <ul className="market-status-list">
            {visibleRows.map((row) => (
              <li className="market-status-row" key={row.currency}>
                <div className="market-row-title">
                  <strong>{row.currency}</strong>
                  <span>{row.method}</span>
                </div>
                <dl>
                  <HistoryMetric label="樣本數" value={String(row.sample_count)} />
                  <HistoryMetric label="第一層樣本" value={String(row.top_level_sample_count)} />
                  <HistoryMetric label="最低樣本" value={String(row.min_samples)} />
                  <HistoryMetric label="最新資料" value={formatTimestamp(row.latest_captured_at, timeZone)} />
                  <HistoryMetric label="建議日利率" value={rate(row.suggested_min_daily_rate)} />
                  <HistoryMetric label="狀態原因" value={reasonLabel(row.reason)} />
                </dl>
              </li>
            ))}
          </ul>
          <PaginationControls
            currentPage={currentPage}
            totalPages={totalPages}
            totalRows={rows.length}
            pageSize={pageSize}
            onPageChange={setPage}
          />
        </>
      )}
    </section>
  )
}

function MarketRateList({ rows, timeZone, exchange }: { rows: MarketRate[]; timeZone: string; exchange: string }) {
  const latestRows = latestMarketRatesByCurrency(rows)

  return (
    <MarketRecordList
      title="市場利率快照"
      description={`從 ${exchange} lendbook 取得後寫入 market_rates，每個幣別只顯示最新一筆。`}
      emptyText="目前沒有市場利率資料。"
        rows={latestRows.map((row) => ({
          id: row.id,
          title: row.currency,
          currency: row.currency,
          fields: [
            ['日利率', rate(row.daily_rate)],
            ['可用數量', amount(row.available_amount)],
          ['擷取時間', formatTimestamp(row.captured_at, timeZone)],
        ],
      }))}
    />
  )
}

function latestMarketRatesByCurrency(rows: MarketRate[]): MarketRate[] {
  const latestRows = new Map<string, MarketRate>()
  for (const row of rows) {
    const previousRow = latestRows.get(row.currency)
    if (!previousRow || row.captured_at > previousRow.captured_at) {
      latestRows.set(row.currency, row)
    }
  }

  return Array.from(latestRows.values()).sort((left, right) => left.currency.localeCompare(right.currency))
}

function MarketDepthList({ rows, timeZone, exchange }: { rows: MarketAnalysisRate[]; timeZone: string; exchange: string }) {
  const latestRows = latestMarketAnalysisRowsByCurrency(rows)

  return (
    <MarketRecordList
      title="市場分析紀錄"
      description={`由市場分析操作從 ${exchange} 記錄的多層放貸簿深度資料，每個幣別只顯示最新一輪。`}
      emptyText="目前沒有市場分析紀錄。"
      rows={latestRows.map((row) => ({
        id: row.id,
        title: `${row.currency} / 第 ${row.level} 層`,
        currency: row.currency,
        fields: [
          ['日利率', rate(row.daily_rate)],
          ['可用數量', amount(row.available_amount)],
          ['擷取時間', formatTimestamp(row.captured_at, timeZone)],
        ],
      }))}
    />
  )
}

function latestMarketAnalysisRowsByCurrency(rows: MarketAnalysisRate[]): MarketAnalysisRate[] {
  const latestCapturedAtByCurrency = new Map<string, string>()
  for (const row of rows) {
    const previousCapturedAt = latestCapturedAtByCurrency.get(row.currency)
    if (!previousCapturedAt || row.captured_at > previousCapturedAt) {
      latestCapturedAtByCurrency.set(row.currency, row.captured_at)
    }
  }

  return rows
    .filter((row) => row.captured_at === latestCapturedAtByCurrency.get(row.currency))
    .sort((left, right) => {
      const currencyComparison = left.currency.localeCompare(right.currency)
      return currencyComparison || left.level - right.level
    })
}

function MarketRecordList({
  title,
  description,
  emptyText,
  rows,
}: {
  title: string
  description: string
  emptyText: string
  rows: Array<{ id: number; title: string; currency: string; fields: Array<[string, string]> }>
}) {
  const [page, setPage] = useState(1)
  const [selectedCurrency, setSelectedCurrency] = useState('all')
  const [searchText, setSearchText] = useState('')
  const pageSize = 10
  const currencyOptions = Array.from(new Set(rows.map((row) => row.currency))).sort()
  const filteredRows = rows.filter((row) => {
    const matchesCurrency = selectedCurrency === 'all' || row.currency === selectedCurrency
    const normalizedSearch = searchText.trim().toLowerCase()
    const matchesSearch = normalizedSearch
      ? [row.title, ...row.fields.flatMap(([label, value]) => [label, value])]
          .join(' ')
          .toLowerCase()
          .includes(normalizedSearch)
      : true
    return matchesCurrency && matchesSearch
  })
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const visibleRows = filteredRows.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const changeCurrency = (currency: string) => {
    setSelectedCurrency(currency)
    setPage(1)
  }
  const changeSearchText = (value: string) => {
    setSearchText(value)
    setPage(1)
  }

  return (
    <section className="market-panel">
      <div className="section-heading compact">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <span>{rows.length} 筆</span>
      </div>
      {rows.length > 0 ? (
        <div className="market-filter-bar">
          <label>
            <span>幣別</span>
            <select value={selectedCurrency} onChange={(event) => changeCurrency(event.currentTarget.value)}>
              <option value="all">全部幣別</option>
              {currencyOptions.map((currency) => (
                <option key={currency} value={currency}>{currency}</option>
              ))}
            </select>
          </label>
          <label>
            <span>搜尋</span>
            <input
              type="search"
              value={searchText}
              placeholder="輸入層級、利率、數量或時間"
              onChange={(event) => changeSearchText(event.currentTarget.value)}
            />
          </label>
          <strong>{filteredRows.length} 筆符合</strong>
        </div>
      ) : null}
      {rows.length === 0 ? (
        <p className="empty-hint padded">{emptyText}</p>
      ) : filteredRows.length === 0 ? (
        <p className="empty-hint padded">沒有符合篩選條件的資料。</p>
      ) : (
        <>
          <div className="market-table-scroll">
            <table className="market-record-table">
              <thead>
                <tr>
                  <th>項目</th>
                  {rows[0]?.fields.map(([label]) => <th key={label}>{label}</th>)}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.title}</td>
                    {row.fields.map(([label, value]) => <td key={label}>{value}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PaginationControls
            currentPage={currentPage}
            totalPages={totalPages}
            totalRows={filteredRows.length}
            pageSize={pageSize}
            onPageChange={setPage}
          />
        </>
      )}
    </section>
  )
}

function OffersSummaryPanel({ offers, openOffers }: { offers: LoanOffer[]; openOffers: LoanOffer[] }) {
  const currencies = new Set(offers.map((offer) => offer.currency)).size
  const dryRunCount = offers.filter((offer) => offer.dry_run).length
  return (
    <section className="offers-summary-panel">
      <div>
        <p className="eyebrow">委託總覽</p>
        <h2>{offers.length}</h2>
        <p>本頁只顯示本地與交易所委託狀態，不提供同步或取消操作。</p>
      </div>
      <div className="offers-summary-metrics">
        <OverviewMetric label="本地委託" value={offers.length} />
        <OverviewMetric label="未成交快照" value={openOffers.length} />
        <OverviewMetric label="涵蓋幣種" value={currencies} />
        <OverviewMetric label="模擬委託" value={dryRunCount} />
      </div>
    </section>
  )
}

function OfferListPanel({
  title,
  description,
  rows,
  timeZone,
  actionLabel,
  actionPending = false,
  onCancelOffer,
}: {
  title: string
  description: string
  rows: LoanOffer[]
  timeZone: string
  actionLabel?: string
  actionPending?: boolean
  onCancelOffer?: (offer: LoanOffer) => void
}) {
  const [page, setPage] = useState(1)
  const pageSize = 10
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const visibleRows = rows.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  return (
    <section className="offer-list-panel">
      <div className="section-heading compact">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <span>{rows.length} 筆</span>
      </div>
      {rows.length === 0 ? (
        <p className="empty-hint padded">目前沒有委託資料。</p>
      ) : (
        <>
          <div className="offer-table-scroll">
            <table className="offer-table">
              <thead>
                <tr>
                  <th>編號</th>
                  <th>幣種</th>
                  <th>數量</th>
                  <th>日利率</th>
                  <th>天數</th>
                  <th>狀態</th>
                  <th>模式</th>
                  <th>交易所編號</th>
                  <th>時間</th>
                  {onCancelOffer ? <th>操作</th> : null}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((offer) => (
                  <tr key={offer.id}>
                    <td>{offer.id}</td>
                    <td>{offer.currency}</td>
                    <td>{amount(offer.amount)}</td>
                    <td>{rate(offer.daily_rate)}</td>
                    <td>{offer.duration_days} 天</td>
                    <td>{statusLabel(offer.status ?? '-')}</td>
                    <td>{offer.dry_run ? '模擬' : 'Live'}</td>
                    <td>{offer.external_offer_id ?? '-'}</td>
                    <td>{offer.captured_at ? formatTimestamp(offer.captured_at, timeZone) : '-'}</td>
                    {onCancelOffer ? (
                      <td>
                        <button
                          type="button"
                          className="inline-danger-button"
                          disabled={actionPending || !offer.external_offer_id}
                          onClick={() => onCancelOffer(offer)}
                        >
                          {actionLabel ?? '操作'}
                        </button>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PaginationControls
            currentPage={currentPage}
            totalPages={totalPages}
            totalRows={rows.length}
            pageSize={pageSize}
            onPageChange={setPage}
          />
        </>
      )}
    </section>
  )
}

function CancelOfferConfirmModal({
  offer,
  onCancel,
  onConfirm,
}: {
  offer: LoanOffer
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="run-flow-modal" role="dialog" aria-modal="true" aria-labelledby="cancel-offer-title">
        <div className="modal-heading">
          <div>
            <p className="eyebrow">Live 取消確認</p>
            <h2 id="cancel-offer-title">取消單筆放貸委託</h2>
            <p>
              這會對交易所送出取消委託：{offer.currency} {amount(offer.amount)}，編號 {offer.external_offer_id}。
            </p>
          </div>
        </div>
        <div className="modal-actions">
          <button type="button" className="secondary-button" onClick={onCancel}>先不要</button>
          <button type="button" className="danger-button" onClick={onConfirm}>確認取消委託</button>
        </div>
      </section>
    </div>
  )
}

function PaginationControls({
  currentPage,
  totalPages,
  totalRows,
  pageSize,
  onPageChange,
}: {
  currentPage: number
  totalPages: number
  totalRows: number
  pageSize: number
  onPageChange: (page: number) => void
}) {
  const start = (currentPage - 1) * pageSize + 1
  const end = Math.min(currentPage * pageSize, totalRows)

  return (
    <div className="pagination-controls">
      <span>
        顯示 {start}-{end} / {totalRows} 筆
      </span>
      <div>
        <button type="button" disabled={currentPage <= 1} onClick={() => onPageChange(currentPage - 1)}>
          上一頁
        </button>
        <strong>{currentPage} / {totalPages}</strong>
        <button
          type="button"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
        >
          下一頁
        </button>
      </div>
    </div>
  )
}

function StrategyDecisionPanel({ decisions }: { decisions: StrategyDecision[] }) {
  const [expandedCurrency, setExpandedCurrency] = useState<string | null>(null)

  return (
    <section className="strategy-decision-panel">
      <div className="section-heading">
        <div>
          <h2>策略決策</h2>
          <p>每個幣別目前套用的策略、利率門檻與預計建立的委託。</p>
        </div>
        <span>{decisions.length} 筆</span>
      </div>

      {decisions.length === 0 ? (
        <p className="strategy-empty">目前沒有策略決策資料</p>
      ) : (
        <div className="strategy-table-scroll">
          <table className="strategy-table">
            <thead>
              <tr>
                <th>幣種</th>
                <th>可用餘額</th>
                <th>放貸中</th>
                <th>最佳市場日利率</th>
                <th>有效最低日利率</th>
                <th>預計</th>
                <th>原因</th>
                <th>明細</th>
              </tr>
            </thead>
            <tbody>
              {decisions.map((decision) => {
                const isExpanded = expandedCurrency === decision.currency
                return (
                  <>
                    <tr key={decision.currency}>
                      <td>{decision.currency}</td>
                      <td>{amount(decision.balance)}</td>
                      <td>{amount(decision.active_amount)}</td>
                      <td>{rate(decision.best_market_rate)}</td>
                      <td>{rate(decision.effective_min_daily_rate)}</td>
                      <td>{decision.offer_count > 0 ? `${decision.offer_count} 筆` : '-'}</td>
                      <td>{reasonLabel(decision.reason)}</td>
                      <td>
                        <button
                          type="button"
                          className="table-inline-button"
                          onClick={() => setExpandedCurrency(isExpanded ? null : decision.currency)}
                        >
                          {isExpanded ? '收合' : '查看'}
                        </button>
                      </td>
                    </tr>
                    {isExpanded ? (
                      <tr className="strategy-detail-row" key={`${decision.currency}-details`}>
                        <td colSpan={8}>
                          <div className="strategy-detail-stack">
                            <div className="strategy-detail-grid">
                              <HistoryMetric label="未成交委託" value={amount(decision.open_offer_amount)} />
                              <HistoryMetric label="最高日利率" value={rate(decision.max_daily_rate)} />
                              <HistoryMetric label="最大可放貸" value={amount(decision.max_to_lend)} />
                              <HistoryMetric label="最大放貸中" value={amount(decision.max_active_amount)} />
                            </div>
                            <div className="strategy-offer-panel">
                              <strong>預計委託</strong>
                              <DecisionOfferList offers={decision.offers} offerCount={decision.offer_count} />
                            </div>
                            <div className="strategy-offer-panel">
                              <strong>候選利率與期望分數</strong>
                              <DecisionRateCandidateList candidates={decision.rate_candidates} />
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
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
  max_offer_amount: '單筆最大委託金額',
  min_offer_remainder: '尾款保留門檻',
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
  allow_above_market_offers: '低於市場時仍用最低利率掛單',
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
  'Created minimum-rate offers while market is below the configured minimum.': '市場低於最低要求，已依設定用有效最低利率先建立預計委託。',
  'No loan orders are available.': '目前沒有可參考的放貸簿委託。',
  'Available balance is below the minimum loan size.': '可用餘額低於最低放貸金額。',
  'Active lending amount is at or above the configured maximum.': '放貸中金額已達或超過設定上限。',
  'Best daily rate is below the configured minimum.': '最佳日利率低於設定的最低日利率。',
  'End date is too close to create new lending offers.': '停止放貸日期太近，不能建立新委託。',
  'Market analysis is disabled.': '策略分析方法已關閉，仍會收集市場資料。',
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

function historyModeLabel(value: unknown): string {
  return value ? '模擬' : '真實'
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

const offerColumns = [
  { key: 'id', label: '編號' },
  { key: 'currency', label: '幣種' },
  { key: 'amount', label: '數量', format: amount },
  { key: 'daily_rate', label: '日利率', format: rate },
  { key: 'duration_days', label: '天數' },
  { key: 'status', label: '狀態', format: statusLabel },
  { key: 'external_offer_id', label: '交易所編號' },
] satisfies Parameters<typeof DataTable<LoanOffer>>[0]['columns']
