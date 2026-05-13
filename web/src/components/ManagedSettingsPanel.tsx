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
      setMessage(`已儲存 ${result.changed_count} 個設定。下一次 API 動作或 bot loop 會套用。`)
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
      setMessage('已匯出設定 JSON。Secret 欄位不會包含在匯出檔。')
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
          <p className="eyebrow">SaaS Settings</p>
          <h2>Bot 設定管理</h2>
          <p>讀取 SQLite 中的覆寫值；儲存後會在下一次 API 動作或 bot loop 熱更新。</p>
        </div>
        <label className="admin-token-field">
          <span>Admin Token</span>
          <input
            type="password"
            value={adminToken}
            placeholder="ADMIN_AUTH_TOKEN"
            onChange={(event) => onAdminTokenChange(event.currentTarget.value)}
          />
        </label>
      </div>

      {isLoading ? <p className="settings-state">讀取設定 schema...</p> : null}
      {queryError ? <p className="settings-state error">{(queryError as Error).message}</p> : null}

      {data ? (
        <div className="settings-editor">
          <div className="settings-filter-bar">
            <label>
              <span>搜尋設定</span>
              <input
                type="search"
                value={searchText}
                placeholder="例如 BOT_DRY_RUN、rate、telegram"
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
              但請先保持 BOT_DRY_RUN=true 完成驗證。
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
        <strong>{definition.key}</strong>
        <small>{dangerLabels[definition.danger_level]}</small>
      </span>
      {valueType === 'bool' ? (
        <select value={value} disabled={disabled} onChange={(event) => onChange(event.currentTarget.value)}>
          <option value="true">true</option>
          <option value="false">false</option>
        </select>
      ) : valueType === 'enum' && definition.choices.length ? (
        <select value={value} disabled={disabled} onChange={(event) => onChange(event.currentTarget.value)}>
          {definition.choices.map((choice) => (
            <option value={choice} key={choice}>
              {choice}
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
        {definition.secret && storedValue?.is_set ? '已設定 secret；留空代表不變。' : `預設值：${definition.default || '(空值)'}`}
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

  return [definition.key, definition.category, definition.value_type, definition.description]
    .join(' ')
    .toLowerCase()
    .includes(normalizedSearch)
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
