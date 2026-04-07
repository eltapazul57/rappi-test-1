/**
 * API client — all requests proxied through Vite to http://localhost:8000
 */

const BASE = '/api'

/** @returns {Promise<{answer: string, data: Array, sql: string|null, session_id: string}>} */
export async function sendMessage(message, sessionId) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId ?? null }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail ?? `Server error ${res.status}`)
  }
  return res.json()
}

/** @returns {Promise<{report: string}>} */
export async function generateInsights() {
  const res = await fetch(`${BASE}/insights`, { method: 'POST' })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail ?? `Server error ${res.status}`)
  }
  return res.json()
}
