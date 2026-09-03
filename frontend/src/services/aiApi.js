const AI_API_BASE = import.meta.env.VITE_AI_API_BASE_URL || '/ai-api'

export class AiApiError extends Error {
  constructor(message, { code = null, retryable = false, status = 0 } = {}) {
    super(message)
    this.name = 'AiApiError'
    this.code = code
    this.retryable = retryable
    this.status = status
  }
}

function requestError(body, status, fallback) {
  const detail = body.detail || body
  return new AiApiError(detail.message || body.message || fallback, {
    code: detail.code || body.code || null,
    retryable: Boolean(detail.retryable || body.retryable),
    status,
  })
}

export async function askAi(question, sessionId = null) {
  const endpoint = sessionId ? `${AI_API_BASE}/chat/${encodeURIComponent(sessionId)}` : `${AI_API_BASE}/chat`
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ question }),
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw requestError(body, response.status, `AI 请求失败（${response.status}）`)
  }
  return body
}

export async function fetchDueDiligence(projectId) {
  const response = await fetch(`${AI_API_BASE}/due-diligence/${encodeURIComponent(projectId)}`, {
    headers: { Accept: 'application/json' },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw requestError(body, response.status, `尽调请求失败（${response.status}）`)
  }
  return body
}

export async function clearFinanceAssumptions(sessionId) {
  const response = await fetch(`${AI_API_BASE}/chat/${encodeURIComponent(sessionId)}/assumptions`, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw requestError(body, response.status, `清除融资假设失败（${response.status}）`)
  return body
}

export async function resetConversationContext(sessionId) {
  const response = await fetch(`${AI_API_BASE}/chat/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw requestError(body, response.status, `重置上下文失败（${response.status}）`)
  return body
}
