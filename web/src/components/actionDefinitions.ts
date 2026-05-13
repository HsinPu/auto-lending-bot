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
    action: 'record-market-analysis',
    label: '記錄市場分析',
    description: '記錄設定幣種清單的 lendbook levels。',
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
    action: 'run-once',
    label: '執行一次',
    description: '觸發一次 bot run；Live 模式需要二次確認。',
  },
]
