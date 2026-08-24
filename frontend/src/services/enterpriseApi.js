const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

async function request(path) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { Accept: 'application/json' } })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const body = await response.json()
      message = body.message || body.detail || message
    } catch {
      // Keep the HTTP status message when the server did not return JSON.
    }
    throw new Error(message)
  }
  return response.json()
}

export function fetchEnterprises(query = '', limit = 200) {
  const params = new URLSearchParams({ query, limit: String(limit) })
  return request(`/enterprises?${params}`)
}

export function fetchEnterprise(companyId) {
  return request(`/enterprises/${encodeURIComponent(companyId)}`)
}

export function fetchHomeSummary() {
  return request('/enterprises/home-summary')
}

export function fetchPowerSourceOverview() {
  return request('/power-source-structure/overview')
}

export function fetchLoadPriceWindow(companyId, year = 2025) {
  return request(`/enterprises/${encodeURIComponent(companyId)}/load-price-window?year=${encodeURIComponent(year)}`)
}

export function fetchHourlyLoad(companyId, { year, page = 0, size = 24 } = {}) {
  const params = new URLSearchParams({ page: String(page), size: String(size) })
  if (year) params.set('year', String(year))
  return request(`/enterprises/${encodeURIComponent(companyId)}/hourly-load?${params}`)
}

export function fetchHourlyGeneration(companyId, { year, page = 0, size = 24 } = {}) {
  const params = new URLSearchParams({ page: String(page), size: String(size) })
  if (year) params.set('year', String(year))
  return request(`/enterprises/${encodeURIComponent(companyId)}/hourly-generation?${params}`)
}

export function fetchReferenceData(dataset, { query = '', page = 0, size = 20 } = {}) {
  const params = new URLSearchParams({ query, page: String(page), size: String(size) })
  return request(`/reference-data/${encodeURIComponent(dataset)}?${params}`)
}
