import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  exportManagedSettings,
  getManagedSettings,
  importManagedSettings,
  resetManagedSetting,
  updateManagedSettings,
} from '../api/client'
import type {
  ManagedSettingDefinition,
  ManagedSettingScope,
  ManagedSettingsExport,
  ManagedSettingValue,
} from '../types/api'

type ManagedSettingsPanelProps = {
  adminToken: string
  onAdminTokenChange: (token: string) => void
}

const categoryLabels: Record<string, string> = {
  Advanced: '進階',
  Exchange: '交易所',
  General: '一般',
  'Market Analysis': '市場分析',
  Notifications: '通知',
  Operations: '操作',
  Safety: '安全',
  Strategy: '策略',
  Transfers: '資金轉移',
}

const dangerLabels = {
  normal: '一般',
  high: '高風險',
  critical: '關鍵風險',
}

const scopeLabels: Record<ManagedSettingDefinition['scope'], string> = {
  global: '全域',
  profile: 'Profile',
  profile_secret: 'Profile 密鑰',
  profile_safety: 'Profile 安全',
}

type SettingScopeFilter = 'all' | ManagedSettingScope

const scopeFilterOptions: Array<{ value: SettingScopeFilter; label: string }> = [
  { value: 'all', label: '全部範圍' },
  { value: 'global', label: scopeLabels.global },
  { value: 'profile', label: scopeLabels.profile },
  { value: 'profile_secret', label: scopeLabels.profile_secret },
  { value: 'profile_safety', label: scopeLabels.profile_safety },
]

const settingLabels: Record<string, string> = {
  ALLOW_BALANCE_TRANSFERS: '允許資金轉移',
  ALLOW_LIVE_TRADING: '允許 Live 交易',
  AUTO_CANCEL_OPEN_OFFERS: '自動取消未成交委託',
  AUTO_REBALANCE_OPEN_OFFERS: '自動重整未成交委託',
  BITFINEX_ENABLE_LIVE_OFFERS: '啟用 Bitfinex Live 放貸',
  BITFINEX_ENABLE_LIVE_TRANSFERS: '啟用 Bitfinex Live 轉帳',
  BOT_DRY_RUN: '模擬模式',
  BOT_INACTIVE_SLEEP_SECONDS: '無委託時等待秒數',
  BOT_LABEL: 'Bot 名稱',
  BOT_MAX_LOOPS: '最大執行迴圈數',
  BOT_SLEEP_SECONDS: '一般等待秒數',
  DISPLAY_TIMEZONE: '顯示時區',
  END_DATE: '停止放貸日期',
  EXCHANGE: '交易所',
  EXCHANGE_API_KEY: '交易所 API Key',
  EXCHANGE_API_SECRET: '交易所 API Secret',
  FRR_AS_MIN: '使用 FRR 作為最低利率',
  FRR_DELTA: 'FRR 調整值',
  GAP_BOTTOM: 'Gap 下緣深度',
  GAP_MODE: 'Gap 模式',
  GAP_TOP: 'Gap 上緣深度',
  HIDE_COINS: '低於最低利率時保留資金',
  HTTP_TIMEOUT_SECONDS: 'HTTP 逾時秒數',
  KEEP_STUCK_ORDERS: '保留卡住的小額委託',
  LOG_LEVEL: 'Log 等級',
  MARKET_ANALYSIS_CURRENCIES: '市場分析幣別',
  MARKET_ANALYSIS_INTERVAL_SECONDS: '市場資料收集間隔秒數',
  MARKET_ANALYSIS_LEVELS: '市場分析深度層數',
  MARKET_ANALYSIS_MACD_LONG_SAMPLES: 'MACD 長週期樣本數',
  MARKET_ANALYSIS_MACD_LONG_SECONDS: 'MACD 長週期秒數',
  MARKET_ANALYSIS_MACD_SHORT_SAMPLES: 'MACD 短週期樣本數',
  MARKET_ANALYSIS_MACD_SHORT_SECONDS: 'MACD 短週期秒數',
  MARKET_ANALYSIS_MAX_AGE_SECONDS: '市場分析資料最大秒數',
  MARKET_ANALYSIS_METHOD: '市場分析方法',
  MARKET_ANALYSIS_MIN_SAMPLES: '市場分析最低樣本數',
  MARKET_ANALYSIS_MULTIPLIER: '市場分析倍率',
  MARKET_ANALYSIS_PERCENTILE: '市場分析百分位',
  MARKET_ANALYSIS_RETENTION_DAYS: '市場分析保留天數',
  MARKET_RATE_RETENTION_DAYS: '市場利率保留天數',
  MAX_ACTIVE_AMOUNT: '最大放貸中金額',
  MAX_AMOUNT_TO_LEND: '最大可放貸金額',
  MAX_DAILY_RATE: '最高日利率',
  MAX_OFFER_AMOUNT: '單筆最大委託金額',
  MAX_PERCENT_TO_LEND: '最大放貸百分比',
  MAX_SINGLE_OFFER_AMOUNT: '單筆委託上限',
  MAX_SINGLE_TRANSFER_AMOUNT: '單筆轉帳上限',
  MAX_TO_LEND: '最大可放貸金額',
  MAX_TO_LEND_RATE: 'Max-to-lend 啟用利率',
  MAX_TOTAL_LEND_AMOUNT: '單次執行總放貸上限',
  MAX_TOTAL_TRANSFER_AMOUNT: '單次執行總轉帳上限',
  MIN_DAILY_RATE: '最低日利率',
  MIN_LOAN_SIZE: '最低放貸金額',
  MIN_OFFER_REMAINDER: '尾款保留門檻',
  NOTIFY_CAUGHT_EXCEPTION: '錯誤通知',
  NOTIFY_PREFIX: '通知前綴',
  NOTIFY_SUMMARY_MINUTES: '摘要通知間隔分鐘',
  NOTIFY_XDAY_THRESHOLD: '長天期委託通知',
  OUTPUT_CURRENCY: '收益換算幣別',
  RETRY_ATTEMPTS: '重試次數',
  RETRY_BACKOFF_SECONDS: '重試等待秒數',
  SMOKE_TEST_CURRENCY: '測試幣別',
  SPREAD_LEND: '委託拆單數',
  STRATEGY_DEBUG: '策略除錯模式',
  TELEGRAM_BOT_TOKEN: 'Telegram Bot Token',
  TELEGRAM_CHAT_ID: 'Telegram Chat ID',
  TRANSFERABLE_CURRENCIES: '可轉移幣別',
  XDAY_SPREAD: '長天期線性區間',
  XDAY_THRESHOLD: '長天期利率門檻',
  XDAYS: '長天期天數',
}

const choiceLabels: Record<string, string> = {
  false: '否',
  true: '是',
  mock: '模擬交易所',
  bitfinex: 'Bitfinex',
  off: '關閉',
  raw: '原始深度',
  relative: '相對比例',
  raw_btc: 'BTC 原始深度',
  rawbtc: 'BTC 原始深度',
  percentile: '百分位',
  macd: 'MACD 均線',
}

const settingHelp: Record<string, string> = {
  ALLOW_BALANCE_TRANSFERS: '是否允許 bot 執行交易所帳戶到放貸帳戶的資金轉移。Live 轉帳必須開啟。',
  ALLOW_LIVE_TRADING: 'Live 模式總開關。關閉時，即使其他 Live 設定開啟也不會執行真實操作。',
  AUTO_CANCEL_OPEN_OFFERS: '自動重整未成交委託時，是否真的取消交易所上的舊委託。',
  AUTO_REBALANCE_OPEN_OFFERS: '每次執行時是否先同步並重整未成交委託。',
  BITFINEX_ENABLE_LIVE_OFFERS: 'Bitfinex 真實建立放貸委託的最後一道開關。',
  BITFINEX_ENABLE_LIVE_TRANSFERS: 'Bitfinex 真實資金轉移的最後一道開關。',
  BOT_DRY_RUN: '建議保持「是」。是 = 只模擬、不送出真實委託；否 = 可能進入 Live 操作。',
  BOT_INACTIVE_SLEEP_SECONDS: '沒有可建立委託時，下一輪執行前等待幾秒。',
  BOT_LABEL: 'Dashboard 與狀態列顯示的 bot 名稱。',
  BOT_MAX_LOOPS: '執行幾輪後停止。0 或負數代表持續執行。',
  BOT_SLEEP_SECONDS: '有建立委託時，下一輪執行前等待幾秒。',
  DISPLAY_TIMEZONE: 'Dashboard 顯示時間用的時區，例如 Asia/Taipei。資料庫仍保存 UTC。',
  END_DATE: '到這天前停止建立新長天期委託，格式 YYYY-MM-DD。',
  EXCHANGE: '目前交易所。mock 用於本機測試；bitfinex 才會連真實 Bitfinex。',
  EXCHANGE_API_KEY: '交易所 API Key。建議使用沒有提領權限的 key。',
  EXCHANGE_API_SECRET: '交易所 API Secret，會加密存入 SQLite。',
  FRR_AS_MIN: '是否把 Bitfinex FRR 當作最低日利率參考。',
  FRR_DELTA: '在 FRR 基礎上加減的日利率差值。',
  GAP_BOTTOM: '委託利率區間下緣使用的放貸簿深度。',
  GAP_MODE: '決定 GAP_BOTTOM/GAP_TOP 如何解讀。關閉時使用最佳市場利率。',
  GAP_TOP: '委託利率區間上緣使用的放貸簿深度。',
  HIDE_COINS: '市場利率低於最低利率時，是否先保留資金不放貸。',
  ALLOW_ABOVE_MARKET_OFFERS: '市場利率低於有效最低利率時，是否仍用有效最低利率先掛單。',
  HTTP_TIMEOUT_SECONDS: '呼叫交易所或外部 API 的逾時秒數。',
  KEEP_STUCK_ORDERS: '小於最低放貸金額的殘留委託是否保留，避免取消後無法再放。',
  LOG_LEVEL: '後端 log 詳細程度。一般使用 INFO。',
  MARKET_ANALYSIS_CURRENCIES: '要記錄市場分析的幣別，多個用逗號分隔，例如 BTC,ETH,USDT。',
  MARKET_ANALYSIS_INTERVAL_SECONDS: '啟動背景市場資料收集後，每隔幾秒抓一次放貸簿資料。',
  MARKET_ANALYSIS_LEVELS: '每次記錄放貸簿前幾層資料。',
  MARKET_ANALYSIS_MACD_LONG_SAMPLES: '用樣本數計算 MACD 長週期平均。',
  MARKET_ANALYSIS_MACD_LONG_SECONDS: '用秒數計算 MACD 長週期平均；大於 0 時優先使用。',
  MARKET_ANALYSIS_MACD_SHORT_SAMPLES: '用樣本數計算 MACD 短週期平均。',
  MARKET_ANALYSIS_MACD_SHORT_SECONDS: '用秒數計算 MACD 短週期平均；大於 0 時優先使用。',
  MARKET_ANALYSIS_MAX_AGE_SECONDS: '市場分析資料超過這個秒數就視為過期；0 代表不限制。',
  MARKET_ANALYSIS_METHOD: '市場分析建議最低日利率的方法。關閉時不使用建議利率。',
  MARKET_ANALYSIS_MIN_SAMPLES: '計算建議利率前至少需要多少筆樣本。',
  MARKET_ANALYSIS_MULTIPLIER: '市場分析結果倍率，例如 1.05 代表提高 5%。',
  MARKET_ANALYSIS_PERCENTILE: '百分位方法使用的百分位，例如 75 代表第 75 百分位。',
  MARKET_ANALYSIS_RETENTION_DAYS: '市場分析資料保留幾天。',
  MARKET_RATE_RETENTION_DAYS: '一般市場利率快照保留幾天。',
  MAX_ACTIVE_AMOUNT: '每個幣別最多允許放貸中的金額；空白代表不限制。',
  MAX_AMOUNT_TO_LEND: '最多拿多少金額去放貸；空白代表不限制。',
  MAX_DAILY_RATE: '委託日利率上限，避免掛出太誇張的利率。',
  MAX_OFFER_AMOUNT: '策略拆單時每筆委託最多放多少；空白代表停用，改用固定拆單數。',
  MAX_PERCENT_TO_LEND: '最多拿資金的百分之幾去放貸。100 代表全部可用資金。',
  MAX_SINGLE_OFFER_AMOUNT: 'Live 模式下單筆放貸委託金額上限；0 代表不限制，空白代表未設定。',
  MAX_SINGLE_TRANSFER_AMOUNT: 'Live 模式下單筆轉帳金額上限，必填安全欄位。',
  MAX_TO_LEND: '最多拿多少金額去放貸；建議使用這個 Mika 風格名稱。',
  MAX_TO_LEND_RATE: '市場利率低於或等於此值時，才啟用最大放貸限制；0 代表永遠啟用。',
  MAX_TOTAL_LEND_AMOUNT: 'Live 模式單次執行最多可送出的總放貸金額；0 代表不限制，空白代表未設定。',
  MAX_TOTAL_TRANSFER_AMOUNT: 'Live 模式單次執行最多可轉出的總金額，必填安全欄位。',
  MIN_DAILY_RATE: '低於這個日利率就不放貸，或改用此最低利率掛單。',
  MIN_LOAN_SIZE: '低於這個金額就不建立委託，避免碎單。',
  MIN_OFFER_REMAINDER: '用單筆最大金額拆單時，最後尾款小於或等於此金額就保留不下單。',
  NOTIFY_CAUGHT_EXCEPTION: 'bot 發生錯誤時是否送 Telegram 通知。',
  NOTIFY_PREFIX: '通知訊息前面加上的文字，例如 [LendingBot]。',
  NOTIFY_SUMMARY_MINUTES: '每隔幾分鐘送一次摘要通知；0 代表關閉。',
  NOTIFY_XDAY_THRESHOLD: '建立長天期委託時是否通知。',
  OUTPUT_CURRENCY: '收益換算時使用的目標幣別，例如 BTC 或 USD。',
  RETRY_ATTEMPTS: '交易所/API 操作失敗時最多重試幾次。',
  RETRY_BACKOFF_SECONDS: '每次重試前等待幾秒。',
  SMOKE_TEST_CURRENCY: '連線檢查、設定預覽預設使用的幣別。',
  SPREAD_LEND: '固定拆成幾筆委託；0 代表優先使用單筆最大委託金額自動拆單。',
  STRATEGY_DEBUG: '是否輸出更詳細的策略判斷 log。',
  TELEGRAM_BOT_TOKEN: 'Telegram bot token，設定後才會送通知。',
  TELEGRAM_CHAT_ID: 'Telegram chat id，搭配 bot token 使用。',
  TRANSFERABLE_CURRENCIES: '允許從 exchange 錢包轉到 lending 錢包的幣別，多個用逗號分隔。',
  XDAY_SPREAD: '長天期天數從 2 天逐步增加到 XDAYS 的線性區間。',
  XDAY_THRESHOLD: '日利率達到此門檻時，改用 XDAYS 長天期。',
  XDAYS: '高利率時使用的放貸天數。',
}

const settingHints: Record<string, string> = {
  DISPLAY_TIMEZONE: '選擇 Dashboard 顯示時間；資料庫仍保存 UTC。',
  END_DATE: '格式：YYYY-MM-DD，例如 2026-12-31',
  FRR_DELTA: '日利率小數，例如 0.00001 = 0.001%',
  GAP_BOTTOM: '依 Gap 模式代表金額、BTC 金額或百分比',
  GAP_TOP: '依 Gap 模式代表金額、BTC 金額或百分比',
  MARKET_ANALYSIS_CURRENCIES: '逗號分隔，例如 BTC,ETH,USDT',
  MARKET_ANALYSIS_INTERVAL_SECONDS: '建議先用 60 秒；太短可能打太多交易所 API。',
  MARKET_ANALYSIS_MULTIPLIER: '1 = 不調整；1.05 = 提高 5%',
  MARKET_ANALYSIS_PERCENTILE: '0 到 100，例如 75',
  MAX_DAILY_RATE: '日利率小數，例如 0.05 = 5%',
  MAX_OFFER_AMOUNT: '例如 500；空白代表停用金額拆單',
  MAX_PERCENT_TO_LEND: '百分比數字，例如 100 = 100%',
  MAX_TO_LEND_RATE: '日利率小數，例如 0.0001 = 0.01%',
  MIN_DAILY_RATE: '日利率小數，例如 0.00005 = 0.005%',
  MIN_OFFER_REMAINDER: '例如 100；尾款 100 以內保留不下單',
  NOTIFY_SUMMARY_MINUTES: '0 = 關閉摘要通知',
  OUTPUT_CURRENCY: '範例：BTC、USD、USDT',
  SMOKE_TEST_CURRENCY: '範例：BTC、ETH、USDT',
  TELEGRAM_CHAT_ID: '可以是數字 chat id 或 @channel',
  TRANSFERABLE_CURRENCIES: '逗號分隔，例如 BTC,ETH',
  XDAY_THRESHOLD: '日利率小數，例如 0.002 = 0.2%',
}

const preferredTimeZones = [
  'Asia/Taipei',
  'UTC',
  'Asia/Tokyo',
  'Asia/Seoul',
  'Asia/Hong_Kong',
  'Asia/Singapore',
  'Asia/Shanghai',
  'America/New_York',
  'America/Los_Angeles',
  'Europe/London',
]

type IntlWithSupportedValues = typeof Intl & {
  supportedValuesOf?: (key: 'timeZone') => string[]
}

const commonSettingSections: Array<{
  title: string
  description: string
  keys: string[]
}> = [
  {
    title: '先確認安全模式',
    description: '自己測試時主要看這裡。保持模擬模式就不會送出真實委託。',
    keys: ['BOT_DRY_RUN', 'EXCHANGE', 'BOT_LABEL', 'DISPLAY_TIMEZONE'],
  },
  {
    title: '交易所連線',
    description: '要接 Bitfinex 時才需要填 API key。建議使用沒有提領權限的 key。',
    keys: ['EXCHANGE_API_KEY', 'EXCHANGE_API_SECRET', 'HTTP_TIMEOUT_SECONDS'],
  },
  {
    title: '放貸策略',
    description: '平常最常調的是最低利率、金額限制與拆單數。',
    keys: [
      'MIN_DAILY_RATE',
      'MAX_DAILY_RATE',
      'MIN_LOAN_SIZE',
      'SPREAD_LEND',
      'MAX_OFFER_AMOUNT',
      'MIN_OFFER_REMAINDER',
      'MAX_PERCENT_TO_LEND',
      'MAX_TO_LEND',
    ],
  },
  {
    title: '持續執行頻率',
    description: '從 dashboard 按「開始持續執行」後，這些秒數會影響每輪等待時間。',
    keys: ['BOT_SLEEP_SECONDS', 'BOT_INACTIVE_SLEEP_SECONDS', 'RETRY_ATTEMPTS', 'RETRY_BACKOFF_SECONDS'],
  },
  {
    title: '市場資料收集',
    description: '用來累積市場深度資料，後續百分位與 MACD 策略會靠這些樣本判斷利率。',
    keys: ['MARKET_ANALYSIS_CURRENCIES', 'MARKET_ANALYSIS_INTERVAL_SECONDS', 'MARKET_ANALYSIS_LEVELS'],
  },
  {
    title: 'Live 前保險絲',
    description: '只有要真實下單才需要設定。未確認前不要把模擬模式關掉。',
    keys: [
      'ALLOW_LIVE_TRADING',
      'BITFINEX_ENABLE_LIVE_OFFERS',
      'MAX_TOTAL_LEND_AMOUNT',
      'MAX_SINGLE_OFFER_AMOUNT',
    ],
  },
]

const commonSettingKeys = new Set(commonSettingSections.flatMap((section) => section.keys))

export function ManagedSettingsPanel({
  adminToken,
  onAdminTokenChange,
}: ManagedSettingsPanelProps) {
  const queryClient = useQueryClient()
  const [draftOverrides, setDraftOverrides] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [searchText, setSearchText] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedScope, setSelectedScope] = useState<SettingScopeFilter>('all')
  const [showOnlyOverrides, setShowOnlyOverrides] = useState(false)
  const [settingsMode, setSettingsMode] = useState<'common' | 'advanced'>('common')
  const [confirmResetAll, setConfirmResetAll] = useState(false)
  const { data, isLoading, error: queryError } = useQuery({
    queryKey: ['managed-settings'],
    queryFn: getManagedSettings,
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!data) {
        return { changed_count: 0 }
      }

      const values = Object.fromEntries(
        data.schema
          .filter((definition) =>
            shouldSave(
              definition,
              data.values[definition.key],
              draftValueFor(definition, data.values[definition.key], draftOverrides),
            ),
          )
          .map((definition) => [
            definition.key,
            draftValueFor(definition, data.values[definition.key], draftOverrides),
          ]),
      )
      return updateManagedSettings(values, adminToken)
    },
    onSuccess: async (result) => {
      setDraftOverrides({})
      setMessage(`已儲存 ${result.changed_count} 個設定。下一次 API 動作或 bot 迴圈會套用。`)
      setError(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['managed-settings'] }),
      ])
    },
    onError: (mutationError) => {
      setMessage(null)
      setError((mutationError as Error).message)
    },
  })

  const resetMutation = useMutation({
    mutationFn: (key: string | null) => resetManagedSetting(key, adminToken),
    onSuccess: async (result) => {
      setDraftOverrides({})
      setMessage(`已重設 ${result.reset_count} 個設定。`)
      setError(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['managed-settings'] }),
      ])
    },
    onError: (mutationError) => {
      setMessage(null)
      setError((mutationError as Error).message)
    },
  })
  const exportMutation = useMutation({
    mutationFn: exportManagedSettings,
    onSuccess: (result) => {
      downloadSettingsExport(result)
      setMessage('已匯出設定 JSON。密鑰欄位不會包含在匯出檔。')
      setError(null)
    },
    onError: (mutationError) => {
      setMessage(null)
      setError((mutationError as Error).message)
    },
  })
  const importMutation = useMutation({
    mutationFn: (values: Record<string, string>) => importManagedSettings(values, adminToken),
    onSuccess: async (result) => {
      setDraftOverrides({})
      setMessage(`已匯入 ${result.changed_count} 個設定。`)
      setError(null)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['managed-settings'] }),
      ])
    },
    onError: (mutationError) => {
      setMessage(null)
      setError((mutationError as Error).message)
    },
  })

  const isPending =
    saveMutation.isPending ||
    resetMutation.isPending ||
    exportMutation.isPending ||
    importMutation.isPending
  const categoryOptions = data ? categoryOptionsForMode(data.schema, settingsMode) : []
  const activeCategory = categoryOptions.some((option) => option.value === selectedCategory) ? selectedCategory : 'all'
  const visibleGroups = data
    ? settingsMode === 'common'
      ? groupCommonSettings(
          data.schema,
          data.values,
          draftOverrides,
          searchText,
          activeCategory,
          selectedScope,
          showOnlyOverrides,
        )
      : groupByCategory(
          data.schema.filter((definition) =>
            shouldShowDefinition(
              definition,
              data.values[definition.key],
              draftOverrides,
              searchText,
              activeCategory,
              selectedScope,
              showOnlyOverrides,
              false,
            ),
          ),
        )
    : []
  return (
    <section className="managed-settings-panel" id="managed-settings">
      <div className="section-heading">
        <div>
          <p className="eyebrow">系統設定</p>
          <h2>Bot 設定管理</h2>
          <p>預設只顯示常用設定；儲存後會在下一次 API 動作或 bot 迴圈熱更新。</p>
        </div>
        <label className="admin-token-field">
          <span>後台授權碼（本機可留空）</span>
          <input
            type="password"
            value={adminToken}
            placeholder="遠端後台操作才需要授權碼"
            onChange={(event) => onAdminTokenChange(event.currentTarget.value)}
          />
        </label>
      </div>

      {isLoading ? <p className="settings-state">讀取設定結構...</p> : null}
      {queryError ? <p className="settings-state error">{(queryError as Error).message}</p> : null}

      {data ? (
        <div className="settings-editor">
          <div className="settings-top-spacer" aria-hidden="true" />
          <div className="settings-mode-panel">
            <div>
              <p className="eyebrow">設定模式</p>
              <h3>{settingsMode === 'common' ? '常用設定' : '進階設定'}</h3>
              <p>
                {settingsMode === 'common'
                  ? '只顯示目前最需要調整的項目；從本機 127.0.0.1 使用時可以直接儲存。'
                  : '顯示所有系統參數，包含市場分析、通知、資金轉移與進階策略。'}
              </p>
            </div>
            <div className="settings-mode-buttons" role="group" aria-label="設定顯示模式">
              <button
                type="button"
                className={settingsMode === 'common' ? 'active' : ''}
                onClick={() => {
                  setSettingsMode('common')
                  setSelectedCategory('all')
                }}
              >
                常用設定
              </button>
              <button
                type="button"
                className={settingsMode === 'advanced' ? 'active' : ''}
                onClick={() => {
                  setSettingsMode('advanced')
                  setSelectedCategory('all')
                }}
              >
                全部進階參數
              </button>
            </div>
          </div>
          <div className="settings-filter-bar">
            <label>
              <span>搜尋設定</span>
              <input
                type="search"
                value={searchText}
                placeholder="例如 模擬、利率、Telegram"
                onChange={(event) => setSearchText(event.currentTarget.value)}
              />
            </label>
            <label>
              <span>分類</span>
              <select
                value={activeCategory}
                onChange={(event) => setSelectedCategory(event.currentTarget.value)}
              >
                <option value="all">全部分類</option>
                {categoryOptions.map((category) => (
                  <option value={category.value} key={category.value}>
                    {category.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>設定範圍</span>
              <select
                value={selectedScope}
                onChange={(event) => setSelectedScope(event.currentTarget.value as SettingScopeFilter)}
              >
                {scopeFilterOptions.map((scope) => (
                  <option value={scope.value} key={scope.value}>
                    {scope.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="settings-override-toggle">
              <input
                type="checkbox"
                checked={showOnlyOverrides}
                onChange={(event) => setShowOnlyOverrides(event.currentTarget.checked)}
              />
              只顯示已覆寫或已修改
            </label>
          </div>
          <div className="settings-safety-note">
            <strong>安全提醒</strong>
          <span>
              高風險與關鍵風險設定會影響真實放貸、取消委託或資金轉移。後端仍會套用安全檢查，
              但請先保持「模擬模式 = 是」完成驗證。遠端後台寫入設定仍需要授權碼。
            </span>
          </div>
          {visibleGroups.map(([category, definitions]) => (
            <fieldset className="settings-category" key={category}>
              <legend>{categoryTitle(category)}</legend>
              {categoryDescription(category) ? (
                <p className="settings-category-description">{categoryDescription(category)}</p>
              ) : null}
              <div className="settings-field-grid">
                {definitions.map((definition) => (
                  <SettingField
                    key={definition.key}
                    definition={definition}
                    value={draftValueFor(definition, data.values[definition.key], draftOverrides)}
                    storedValue={data.values[definition.key]}
                    disabled={isPending}
                    showSystemKey={settingsMode === 'advanced'}
                    onChange={(value) =>
                      setDraftOverrides((current) => ({ ...current, [definition.key]: value }))
                    }
                    onReset={() => resetMutation.mutate(definition.key)}
                  />
                ))}
              </div>
            </fieldset>
          ))}
          {visibleGroups.length === 0 ? (
            <p className="settings-state">沒有符合條件的設定。</p>
          ) : null}
        </div>
      ) : null}

      <div className="settings-actions">
        <button
          type="button"
          className="refresh-button"
          disabled={isPending || !data}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending ? '儲存中...' : '儲存變更'}
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={isPending || !data}
          onClick={() => exportMutation.mutate()}
        >
          匯出設定
        </button>
        <label
          className={`secondary-button settings-file-button ${isPending || !data ? 'disabled' : ''}`}
        >
          匯入設定
          <input
            type="file"
            accept="application/json,.json"
            disabled={isPending || !data}
            onChange={(event) => {
              const file = event.currentTarget.files?.[0]
              event.currentTarget.value = ''
              void handleImportFile(file, importMutation.mutate, setError, setMessage)
            }}
          />
        </label>
        <button
          type="button"
          className="secondary-button"
          disabled={isPending || !data}
          onClick={() => setConfirmResetAll(true)}
        >
          全部重設為預設值
        </button>
        {message ? <span className="settings-message">{message}</span> : null}
        {error ? <span className="settings-message error">{error}</span> : null}
      </div>
      {confirmResetAll ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="reset-settings-title">
          <section className="confirm-modal danger">
            <div className="modal-heading">
              <div>
                <p className="eyebrow">重設設定</p>
                <h2 id="reset-settings-title">清除所有 SQLite 設定覆寫值？</h2>
                <p>這會讓所有管理設定回到環境變數或預設值。API Key/Secret 等覆寫值也會被清除。</p>
              </div>
            </div>
            <div className="confirm-actions">
              <button type="button" className="secondary-button" onClick={() => setConfirmResetAll(false)}>取消</button>
              <button
                type="button"
                className="danger-button"
                disabled={isPending}
                onClick={() => {
                  setConfirmResetAll(false)
                  resetMutation.mutate(null)
                }}
              >
                確認重設
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  )
}

type SettingFieldProps = {
  definition: ManagedSettingDefinition
  value: string
  storedValue?: ManagedSettingValue
  disabled: boolean
  showSystemKey: boolean
  onChange: (value: string) => void
  onReset: () => void
}

function SettingField({
  definition,
  value,
  storedValue,
  disabled,
  showSystemKey,
  onChange,
  onReset,
}: SettingFieldProps) {
  const stored = Boolean(storedValue)
  const valueType = definition.secret ? 'secret' : definition.value_type

  return (
    <label className={`settings-field danger-${definition.danger_level}`}>
      <span className="settings-field-heading">
        <strong>{settingLabel(definition.key)}</strong>
        <span className="settings-field-badges">
          <small className={`scope-${definition.scope}`}>{scopeLabels[definition.scope]}</small>
          <small>{dangerLabels[definition.danger_level]}</small>
        </span>
      </span>
      {showSystemKey ? <span className="settings-field-key">系統代碼：{definition.key}</span> : null}
      <span className="settings-field-help">{settingHelpText(definition)}</span>
      {valueType === 'bool' ? (
        <select value={value} disabled={disabled} onChange={(event) => onChange(event.currentTarget.value)}>
          <option value="true">是</option>
          <option value="false">否</option>
        </select>
      ) : valueType === 'enum' && definition.choices.length ? (
        <select value={value} disabled={disabled} onChange={(event) => onChange(event.currentTarget.value)}>
          {definition.choices.map((choice) => (
            <option value={choice} key={choice}>
              {choiceLabels[choice] ?? choice}
            </option>
          ))}
        </select>
      ) : valueType === 'timezone' ? (
        <select value={value} disabled={disabled} onChange={(event) => onChange(event.currentTarget.value)}>
          {timeZoneOptions(value).map((timeZone) => (
            <option value={timeZone} key={timeZone}>
              {timeZoneLabel(timeZone)}
            </option>
          ))}
        </select>
      ) : (
        <input
          type={valueType === 'secret' ? 'password' : inputTypeFor(valueType)}
          step={valueType === 'float' || valueType === 'optional_float' ? 'any' : undefined}
          value={value}
          disabled={disabled}
          placeholder={placeholderFor(definition, storedValue)}
          onChange={(event) => onChange(event.currentTarget.value)}
        />
      )}
      <span className="settings-field-meta">
        {definition.secret && storedValue?.is_set ? '已設定密鑰；留空代表不變。' : `預設值：${defaultDisplayValue(definition)}`}
      </span>
      {settingHints[definition.key] ? (
        <span className="settings-field-hint">{settingHints[definition.key]}</span>
      ) : null}
      <button type="button" className="settings-reset-button" disabled={disabled || !stored} onClick={onReset}>
        重設此項
      </button>
    </label>
  )
}

function groupByCategory(
  definitions: ManagedSettingDefinition[],
): Array<[string, ManagedSettingDefinition[]]> {
  const groups = new Map<string, ManagedSettingDefinition[]>()
  for (const definition of definitions) {
    groups.set(definition.category, [...(groups.get(definition.category) ?? []), definition])
  }

  return Array.from(groups.entries())
}

function categoryOptionsForMode(
  definitions: ManagedSettingDefinition[],
  settingsMode: 'common' | 'advanced',
): Array<{ value: string; label: string }> {
  if (settingsMode === 'common') {
    return commonSettingSections.map((section) => ({ value: section.title, label: section.title }))
  }

  return Array.from(new Set(definitions.map((definition) => definition.category)))
    .sort((left, right) => categoryLabels[left]?.localeCompare(categoryLabels[right] ?? right) ?? left.localeCompare(right))
    .map((category) => ({ value: category, label: categoryLabels[category] ?? category }))
}

function groupCommonSettings(
  definitions: ManagedSettingDefinition[],
  values: Record<string, ManagedSettingValue>,
  draftOverrides: Record<string, string>,
  searchText: string,
  selectedSection: string,
  selectedScope: SettingScopeFilter,
  showOnlyOverrides: boolean,
): Array<[string, ManagedSettingDefinition[]]> {
  const definitionsByKey = new Map(definitions.map((definition) => [definition.key, definition]))

  return commonSettingSections
    .filter((section) => selectedSection === 'all' || section.title === selectedSection)
    .map((section) => [
      section.title,
      section.keys
        .map((key) => definitionsByKey.get(key))
        .filter((definition): definition is ManagedSettingDefinition => Boolean(definition))
        .filter((definition) =>
          shouldShowDefinition(
            definition,
            values[definition.key],
            draftOverrides,
            searchText,
            'all',
            selectedScope,
            showOnlyOverrides,
            true,
          ),
        ),
    ] as [string, ManagedSettingDefinition[]])
    .filter(([, sectionDefinitions]) => sectionDefinitions.length > 0)
}

function currentValue(definition: ManagedSettingDefinition, storedValue?: ManagedSettingValue): string {
  return storedValue?.value ?? definition.default
}

function draftValueFor(
  definition: ManagedSettingDefinition,
  storedValue: ManagedSettingValue | undefined,
  draftOverrides: Record<string, string>,
): string {
  if (Object.hasOwn(draftOverrides, definition.key)) {
    return draftOverrides[definition.key]
  }
  if (definition.secret) {
    return ''
  }

  return currentValue(definition, storedValue)
}

function shouldSave(
  definition: ManagedSettingDefinition,
  storedValue: ManagedSettingValue | undefined,
  draftValue: string,
): boolean {
  if (definition.secret) {
    return draftValue.length > 0
  }

  return draftValue !== currentValue(definition, storedValue)
}

function shouldShowDefinition(
  definition: ManagedSettingDefinition,
  storedValue: ManagedSettingValue | undefined,
  draftOverrides: Record<string, string>,
  searchText: string,
  selectedCategory: string,
  selectedScope: SettingScopeFilter,
  showOnlyOverrides: boolean,
  commonOnly: boolean,
): boolean {
  if (commonOnly && !commonSettingKeys.has(definition.key)) {
    return false
  }
  if (selectedCategory !== 'all' && definition.category !== selectedCategory) {
    return false
  }
  if (selectedScope !== 'all' && definition.scope !== selectedScope) {
    return false
  }
  if (showOnlyOverrides && !storedValue && !Object.hasOwn(draftOverrides, definition.key)) {
    return false
  }

  const normalizedSearch = searchText.trim().toLowerCase()
  if (!normalizedSearch) {
    return true
  }

  return [
    definition.key,
    settingLabel(definition.key),
    settingHelpText(definition),
    settingHints[definition.key],
    definition.category,
    categoryLabels[definition.category],
    scopeLabels[definition.scope],
    definition.value_type,
    definition.description,
  ]
    .join(' ')
    .toLowerCase()
    .includes(normalizedSearch)
}

function settingLabel(key: string): string {
  return settingLabels[key] ?? key
}

function categoryTitle(category: string): string {
  return commonSettingSections.find((section) => section.title === category)?.title ?? categoryLabels[category] ?? category
}

function categoryDescription(category: string): string {
  return commonSettingSections.find((section) => section.title === category)?.description ?? ''
}

function settingHelpText(definition: ManagedSettingDefinition): string {
  return settingHelp[definition.key] ?? definition.description ?? '此設定會影響 bot 執行方式。'
}

function defaultDisplayValue(definition: ManagedSettingDefinition): string {
  if (!definition.default) {
    return '(空值)'
  }

  return choiceLabels[definition.default] ?? definition.default
}

function inputTypeFor(valueType: string): string {
  if (valueType === 'int' || valueType === 'float' || valueType === 'optional_float') {
    return 'number'
  }
  if (valueType === 'date') {
    return 'date'
  }

  return 'text'
}

function timeZoneOptions(currentValue: string): string[] {
  const supportedValues = (Intl as IntlWithSupportedValues).supportedValuesOf?.('timeZone') ?? []
  return Array.from(new Set([currentValue, ...preferredTimeZones, ...supportedValues])).filter(Boolean)
}

function timeZoneLabel(timeZone: string): string {
  if (timeZone === 'UTC') {
    return 'UTC / 世界標準時間'
  }
  if (timeZone === 'Asia/Taipei') {
    return 'Asia/Taipei / 台北時間'
  }

  return timeZone
}

function placeholderFor(
  definition: ManagedSettingDefinition,
  storedValue?: ManagedSettingValue,
): string {
  if (definition.secret && storedValue?.is_set) {
    return `${storedValue.value}，留空不變`
  }

  return definition.default || '(空值)'
}

async function handleImportFile(
  file: File | undefined,
  importValues: (values: Record<string, string>) => void,
  setError: (message: string | null) => void,
  setMessage: (message: string | null) => void,
): Promise<void> {
  if (!file) {
    return
  }

  try {
    const parsed = JSON.parse(await file.text()) as unknown
    importValues(valuesFromImport(parsed))
  } catch (error) {
    setMessage(null)
    setError((error as Error).message)
  }
}

function valuesFromImport(payload: unknown): Record<string, string> {
  if (!payload || typeof payload !== 'object') {
    throw new Error('匯入檔必須是 JSON object。')
  }

  const candidate = 'values' in payload ? payload.values : payload
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
    throw new Error('匯入檔必須包含 values object。')
  }

  return Object.fromEntries(
    Object.entries(candidate).map(([key, value]) => [key, String(value)]),
  )
}

function downloadSettingsExport(payload: ManagedSettingsExport): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'auto-lending-bot-settings.json'
  link.click()
  URL.revokeObjectURL(url)
}
