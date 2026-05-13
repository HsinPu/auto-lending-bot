import { formatAmount } from '../utils/number'

type DataTableProps<T extends Record<string, unknown>> = {
  title: string
  description: string
  rows: T[]
  columns: Array<{
    key: keyof T
    label: string
    format?: (value: T[keyof T], row: T) => string
  }>
}

export function DataTable<T extends Record<string, unknown>>({
  title,
  description,
  rows,
  columns,
}: DataTableProps<T>) {
  return (
    <section className="table-section">
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <span>{rows.length} 筆</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={String(column.key)}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length}>目前沒有資料</td>
              </tr>
            ) : (
              rows.map((row, rowIndex) => (
                <tr key={String(row.id ?? row.currency ?? rowIndex)}>
                  {columns.map((column) => {
                    const value = row[column.key]
                    return (
                      <td key={String(column.key)}>
                        {column.format ? column.format(value, row) : formatValue(value)}
                      </td>
                    )
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : formatAmount(value)
  }
  return String(value)
}
