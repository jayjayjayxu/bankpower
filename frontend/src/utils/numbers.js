// Missing measurements must remain distinct from measured zero.
export function numeric(value) {
  if (value == null || (typeof value === 'string' && value.trim() === '')) return null
  const result = Number(value)
  return Number.isFinite(result) ? result : null
}
export function decimal(value, digits = 2) {
  const result = numeric(value)
  return result == null ? '—' : result.toFixed(digits)
}
export function amount(value, digits = 0) {
  const result = numeric(value)
  return result == null ? '—' : new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  }).format(result)
}
export function percent(value, digits = 1) {
  const result = numeric(value)
  return result == null ? '—' : `${(result * 100).toFixed(digits)}%`
}
export function scaled(value, divisor) {
  const result = numeric(value)
  return result == null ? null : result / divisor
}
