const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

async function request(path) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { Accept: 'application/json' } })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const body = await response.json()
      message = body.message || body.detail || message
    } catch {
      // Keep the HTTP status when the response body is not JSON.
    }
    throw new Error(message)
  }
  return response.json()
}

export function fetchComputeSummary() {
  return request('/compute/summary')
}

export function fetchComputePolicyOverview() {
  return request('/compute/policy/overview')
}

export function fetchFinanceOpportunities() {
  return request('/compute/opportunities')
}

export function fetchFinanceOpportunity(opportunityCode) {
  return request(`/compute/opportunities/${encodeURIComponent(opportunityCode)}`)
}

export function fetchComputeFacilityOperations(facilityCode) {
  return request(`/compute/facilities/${encodeURIComponent(facilityCode)}/operations`)
}

export function fetchComputePowerSynergy(facilityCode) {
  return request(`/compute/power-synergy/${encodeURIComponent(facilityCode)}`)
}

export function fetchCreditPolicies() {
  return request('/compute/credit-policies')
}

export function fetchBankRecommendations({
  query = '', scenarioVersion = 'COMPUTE_BASE_V1', policyCode = 'CREDIT_BASE_V1',
  page = 0, size = 100,
} = {}) {
  const params = new URLSearchParams({ query, scenarioVersion, policyCode, page: String(page), size: String(size) })
  return request(`/compute/bank-recommendations?${params}`)
}

export function fetchComputeSensitivity({ query = '', variableCode = '', page = 0, size = 100 } = {}) {
  const params = new URLSearchParams({ query, variableCode, page: String(page), size: String(size) })
  return request(`/compute/sensitivity?${params}`)
}

export function fetchCreditPolicyCurve(projectEconomicsResultId, policyCode = 'CREDIT_BASE_V1') {
  const params = new URLSearchParams({ policyCode })
  return request(`/compute/bank-recommendations/${projectEconomicsResultId}/curve?${params}`)
}
