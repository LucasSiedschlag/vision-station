/** Numbers as people write them in Portuguese: comma as the decimal mark. */

export function formatNumber(value: number, maxDecimals = 3): string {
  return new Intl.NumberFormat('pt-BR', {
    maximumFractionDigits: maxDecimals,
    useGrouping: false,
  }).format(value)
}
