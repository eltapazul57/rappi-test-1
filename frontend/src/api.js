/**
 * API client — all requests proxied through Vite to http://localhost:8000
 */

const BASE = '/api'

/** @returns {Promise<{answer: string, data: Array, sql: string|null, session_id: string}>} */
export async function sendMessage(message, sessionId) {
  // TODO: implement
  throw new Error('Not implemented')
}

/** @returns {Promise<{report: string}>} */
export async function generateInsights() {
  // TODO: implement
  throw new Error('Not implemented')
}
