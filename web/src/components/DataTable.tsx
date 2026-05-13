import { useState } from 'react'

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
  const [page, setPage] = useState(1)
  const pageSize = 10
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const visibleRows = rows.slice((currentPage - 1) * pageSize, currentPage * pageSize)

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
              visibleRows.map((row, rowIndex) => (
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
      {rows.length > 0 ? (
        <PaginationControls
          currentPage={currentPage}
          totalPages={totalPages}
          totalRows={rows.length}
          pageSize={pageSize}
          onPageChange={setPage}
        />
      ) : null}
    </section>
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

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : formatAmount(value)
  }
  return String(value)
}
