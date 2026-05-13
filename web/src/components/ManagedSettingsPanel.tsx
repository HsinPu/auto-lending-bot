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
  MAX_PERCENT_TO_LEND: '最大放貸百分比',
  MAX_SINGLE_OFFER_AMOUNT: '單筆委託上限',
  MAX_SINGLE_TRANSFER_AMOUNT: '單筆轉帳上限',
  MAX_TO_LEND: '最大可放貸金額',
  MAX_TO_LEND_RATE: 'Max-to-lend 啟用利率',
  MAX_TOTAL_LEND_AMOUNT: '單次執行總放貸上限',
  MAX_TOTAL_TRANSFER_AMOUNT: '單次執行總轉帳上限',
  MIN_DAILY_RATE: '最低日利率',
  MIN_LOAN_SIZE: '最低放貸金額',
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
  const [showOnlyOverrides, setShowOnlyOverrides] = useState(false)
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
  const visibleGroups = data
    ? groupByCategory(
        data.schema.filter((definition) =>
          shouldShowDefinition(
            definition,
            data.values[definition.key],
            draftOverrides,
            searchText,
            selectedCategory,
            showOnlyOverrides,
          ),
        ),
      )
    : []
  const categories = data ? Array.from(new Set(data.schema.map((definition) => definition.category))) : []

  return (
    <section className="managed-settings-panel" id="managed-settings">
      <div className="section-heading">
        <div>
          <p className="eyebrow">SaaS 設定</p>
          <h2>Bot 設定管理</h2>
          <p>讀取 SQLite 中的覆寫值；儲存後會在下一次 API 動作或 bot 迴圈熱更新。</p>
        </div>
        <label className="admin-token-field">
          <span>管理權杖</span>
          <input
            type="password"
            value={adminToken}
            placeholder="ADMIN_AUTH_TOKEN"
            onChange={(event) => onAdminTokenChange(event.currentTarget.value)}
          />
        </label>
      </div>

      {isLoading ? <p className="settings-state">讀取設定結構...</p> : null}
      {queryError ? <p className="settings-state error">{(queryError as Error).message}</p> : null}

      {data ? (
        <div className="settings-editor">
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
                value={selectedCategory}
                onChange={(event) => setSelectedCategory(event.currentTarget.value)}
              >
                <option value="all">全部分類</option>
                {categories.map((category) => (
                  <option value={category} key={category}>
                    {categoryLabels[category] ?? category}
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
              高風險與關鍵風險設定會影響 live 放貸、取消委託或資金轉移。後端仍會套用 safety guard，
              但請先保持「模擬模式 = 是」完成驗證。
            </span>
          </div>
          {visibleGroups.map(([category, definitions]) => (
            <fieldset className="settings-category" key={category}>
              <legend>{categoryLabels[category] ?? category}</legend>
              <div className="settings-field-grid">
                {definitions.map((definition) => (
                  <SettingField
                    key={definition.key}
                    definition={definition}
                    value={draftValueFor(definition, data.values[definition.key], draftOverrides)}
                    storedValue={data.values[definition.key]}
                    disabled={isPending}
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
          disabled={isPending || !adminToken || !data}
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
          className={`secondary-button settings-file-button ${isPending || !adminToken || !data ? 'disabled' : ''}`}
        >
          匯入設定
          <input
            type="file"
            accept="application/json,.json"
            disabled={isPending || !adminToken || !data}
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
          disabled={isPending || !adminToken || !data}
          onClick={() => {
            if (window.confirm('確定要清除所有 SQLite 設定覆寫值？')) {
              resetMutation.mutate(null)
            }
          }}
        >
          全部重設為預設值
        </button>
        {message ? <span className="settings-message">{message}</span> : null}
        {error ? <span className="settings-message error">{error}</span> : null}
      </div>
    </section>
  )
}

type SettingFieldProps = {
  definition: ManagedSettingDefinition
  value: string
  storedValue?: ManagedSettingValue
  disabled: boolean
  onChange: (value: string) => void
  onReset: () => void
}

function SettingField({
  definition,
  value,
  storedValue,
  disabled,
  onChange,
  onReset,
}: SettingFieldProps) {
  const stored = Boolean(storedValue)
  const valueType = definition.secret ? 'secret' : definition.value_type

  return (
    <label className={`settings-field danger-${definition.danger_level}`}>
      <span className="settings-field-heading">
        <strong>{settingLabel(definition.key)}</strong>
        <small>{dangerLabels[definition.danger_level]}</small>
      </span>
      <span className="settings-field-key">{definition.key}</span>
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
  showOnlyOverrides: boolean,
): boolean {
  if (selectedCategory !== 'all' && definition.category !== selectedCategory) {
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
    definition.category,
    categoryLabels[definition.category],
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
