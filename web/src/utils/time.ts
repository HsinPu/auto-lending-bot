export function formatTimestamp(value: unknown, timeZone: string): string {
  const date = parseUtcTimestamp(value)
  if (!date) {
    return '-'
  }

  const resolvedTimeZone = safeTimeZone(timeZone)
  return `${date.toLocaleString('zh-TW', {
    timeZone: resolvedTimeZone,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })} (${resolvedTimeZone})`
}

export function formatTimestampDay(value: unknown, timeZone: string): string {
  const date = parseUtcTimestamp(value)
  if (!date) {
    return '-'
  }

  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: safeTimeZone(timeZone),
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const part = (type: string) => parts.find((entry) => entry.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

function safeTimeZone(timeZone: string): string {
  try {
    Intl.DateTimeFormat(undefined, { timeZone }).format(new Date())
    return timeZone
  } catch {
    return 'UTC'
  }
}

function parseUtcTimestamp(value: unknown): Date | null {
  if (typeof value !== 'string' || !value.trim()) {
    return null
  }

  const normalizedValue = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
    ? value
    : `${value.replace(' ', 'T')}Z`
  const date = new Date(normalizedValue)
  return Number.isNaN(date.getTime()) ? null : date
}
