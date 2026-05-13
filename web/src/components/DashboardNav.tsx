const links = [
  ['status', '狀態'],
  ['actions', '操作'],
  ['managed-settings', '設定'],
  ['coins', '幣種'],
  ['forecast', '推估'],
  ['charts', '摘要'],
  ['profits', '圖表'],
  ['logs', 'Log'],
  ['raw-data', '資料表'],
]

export function DashboardNav({ showRawTables }: { showRawTables: boolean }) {
  return (
    <nav className="dashboard-nav" aria-label="Dashboard sections">
      {links
        .filter(([target]) => showRawTables || target !== 'raw-data')
        .map(([target, label]) => (
          <a href={`#${target}`} key={target}>
            {label}
          </a>
        ))}
    </nav>
  )
}
