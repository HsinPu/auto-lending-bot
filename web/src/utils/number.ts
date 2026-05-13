export function formatAmount(value: unknown, digits = 8): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-'
  }

  return trimFixed(value, digits)
}

export function formatRate(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-'
  }

  return `${trimFixed(value * 100, 6)}%`
}

export function formatPercent(value: unknown): string {
  return formatRate(value)
}

function trimFixed(value: number, digits: number): string {
  if (value === 0) {
    return '0'
  }

  const fixed = value.toFixed(digits)
  const trimmed = fixed.replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1')
  return trimmed === '-0' ? '0' : trimmed
}
