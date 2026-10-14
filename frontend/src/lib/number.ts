/** Numbers as people write them in Portuguese: comma as the decimal mark, optional thousands dots. */

/** Parses "1.234,5", "1234.5", " 12 " ... Returns null when it is empty or not a number. */
export function parseNumber(text: string): number | null {
  const t = text.trim().replace(/\s/g, '')
  if (t === '') return null
  // both marks present: the last one is the decimal mark; only a comma: it is the decimal mark
  let normalised = t
  if (t.includes(',') && t.includes('.')) {
    normalised =
      t.lastIndexOf(',') > t.lastIndexOf('.')
        ? t.replace(/\./g, '').replace(',', '.')
        : t.replace(/,/g, '')
  } else if (t.includes(',')) {
    normalised = t.replace(',', '.')
  }
  if (!/^[+-]?(\d+\.?\d*|\.\d+)$/.test(normalised)) return null
  const value = Number(normalised)
  return Number.isFinite(value) ? value : null
}

export function formatNumber(value: number, maxDecimals = 3): string {
  return new Intl.NumberFormat('pt-BR', {
    maximumFractionDigits: maxDecimals,
    useGrouping: false,
  }).format(value)
}
