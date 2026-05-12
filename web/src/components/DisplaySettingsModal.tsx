import { useState } from 'react'

export type DisplaySettings = {
  compactLayout: boolean
  showRawTables: boolean
}

type DisplaySettingsModalProps = {
  settings: DisplaySettings
  onChange: (settings: DisplaySettings) => void
}

export function DisplaySettingsModal({ settings, onChange }: DisplaySettingsModalProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <button type="button" className="secondary-button" onClick={() => setIsOpen(true)}>
        顯示設定
      </button>

      {isOpen ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setIsOpen(false)}>
          <section
            className="settings-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="display-settings-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-heading">
              <div>
                <h2 id="display-settings-title">顯示設定</h2>
                <p>只影響目前瀏覽器的 dashboard 顯示，不會修改 bot 設定。</p>
              </div>
              <button type="button" className="icon-button" onClick={() => setIsOpen(false)}>
                Close
              </button>
            </div>

            <label className="toggle-row">
              <input
                type="checkbox"
                checked={settings.compactLayout}
                onChange={(event) =>
                  onChange({ ...settings, compactLayout: event.currentTarget.checked })
                }
              />
              <span>
                <strong>精簡間距</strong>
                <small>縮小卡片、表格與區塊 padding，適合長時間監控。</small>
              </span>
            </label>

            <label className="toggle-row">
              <input
                type="checkbox"
                checked={settings.showRawTables}
                onChange={(event) =>
                  onChange({ ...settings, showRawTables: event.currentTarget.checked })
                }
              />
              <span>
                <strong>顯示原始資料表</strong>
                <small>保留 runs、offers、history、market rates 等 API 明細表。</small>
              </span>
            </label>
          </section>
        </div>
      ) : null}
    </>
  )
}
