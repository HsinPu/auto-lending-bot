import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { getManagedSettings, resetManagedSetting, updateManagedSettings } from '../api/client'
import type { ManagedSettingDefinition, ManagedSettingValue } from '../types/api'

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

  const isPending = saveMutation.isPending || resetMutation.isPending

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
          <div className="settings-safety-note">
            <strong>安全提醒</strong>
            <span>
              高風險與關鍵風險設定會影響 live 放貸、取消委託或資金轉移。後端仍會套用 safety guard，
              但請先保持 BOT_DRY_RUN=true 完成驗證。
            </span>
          </div>
          {groupByCategory(data.schema).map(([category, definitions]) => (
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
