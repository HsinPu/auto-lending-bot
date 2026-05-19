import type { SafeActionName } from '../types/api'

export const actions: Array<{ action: SafeActionName; label: string; description: string }> = [
  {
    action: 'smoke-exchange',
    label: '連線檢查',
    description: '讀取餘額與 lendbook，不建立委託。',
  },
  {
    action: 'sync-history',
    label: '同步收益',
    description: '同步目前設定幣種的收益紀錄。',
  },
  {
    action: 'sync-open-offers',
    label: '同步委託',
    description: '同步交易所未成交委託快照。',
  },
  {
    action: 'transfer-preview',
    label: '轉帳預覽',
    description: '預覽 exchange 到 lending 的轉帳，不會移動資金。',
  },
  {
    action: 'transfer-funds',
    label: '執行轉帳',
    description: '依安全限制轉帳到 lending；Live 模式需要二次確認。',
  },
  {
    action: 'record-market-analysis',
    label: '記錄市場分析',
    description: '記錄設定幣種清單的 lendbook levels。',
  },
  {
    action: 'start-market-analysis',
    label: '開始收集市場資料',
    description: '背景定期記錄市場深度，供百分位與 MACD 策略使用。',
  },
  {
    action: 'stop-market-analysis',
    label: '停止收集市場資料',
    description: '停止背景市場資料收集。',
  },
  {
    action: 'cancel-open-offers',
    label: '取消委託',
    description: '取消未成交委託；Live 模式需要二次確認。',
  },
  {
    action: 'cleanup',
    label: '清理資料',
    description: '清理過期市場利率與市場分析紀錄。',
  },
  {
    action: 'reset-dry-run-records',
    label: '重置模擬紀錄',
    description: '刪除本地 dry-run run、決策、步驟與模擬委託，不碰 Live 紀錄。',
  },
  {
    action: 'run-preview',
    label: '執行預覽',
    description: '先看本輪會建立哪些委託，不寫入 run，也不送出交易所操作。',
  },
  {
    action: 'run-once',
    label: '執行一次',
    description: '觸發一次 bot run；Live 模式需要二次確認。',
  },
  {
    action: 'start-loop',
    label: '開始持續執行',
    description: '在目前 API 服務內背景持續偵測與模擬/下單。',
  },
  {
    action: 'stop-loop',
    label: '停止持續執行',
    description: '停止由前端啟動的背景持續執行。',
  },
]
