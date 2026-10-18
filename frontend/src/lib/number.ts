import { currentLocale } from '@/app/locale'

/** Numbers in the interface language: `1234,5` in Portuguese, `1234.5` in English (no grouping). */

export function formatNumber(value: number, maxDecimals = 3): string {
  return new Intl.NumberFormat(currentLocale(), {
    maximumFractionDigits: maxDecimals,
    useGrouping: false,
  }).format(value)
}

/** A fraction as a percentage in the interface language: 0.3 is `30%`. */
export function formatPercent(fraction: number, maxDecimals = 1): string {
  return new Intl.NumberFormat(currentLocale(), {
    style: 'percent',
    maximumFractionDigits: maxDecimals,
    useGrouping: false,
  }).format(fraction)
}
