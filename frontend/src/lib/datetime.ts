import { currentLocale } from '@/app/locale'

/** Dates and times in the interface language: 15/10/2026 14:32, or 10/15/26, 2:32 PM. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat(currentLocale(), {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date)
}

/** Bytes as "2,4 MB". */
export function formatSize(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit++
  }
  return `${new Intl.NumberFormat(currentLocale(), { maximumFractionDigits: unit === 0 ? 0 : 1 }).format(value)} ${units[unit]}`
}
