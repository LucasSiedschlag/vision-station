import { currentLocale } from '@/app/locale'

/** Numbers in the interface language: `1234,5` in Portuguese, `1234.5` in English (no grouping). */

export function formatNumber(value: number, maxDecimals = 3): string {
  return new Intl.NumberFormat(currentLocale(), {
    maximumFractionDigits: maxDecimals,
    useGrouping: false,
  }).format(value)
}
