import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { sendMessage } from '../api'

const SUGGESTIONS = [
  '¿Cuáles son las 5 zonas con mayor Lead Penetration esta semana?',
  'Compara el Perfect Orders entre zonas Wealthy y Non Wealthy en México',
  'Muestra la evolución de Gross Profit UE en Chapinero las últimas 8 semanas',
  '¿Qué zonas tienen alto Lead Penetration pero bajo Perfect Orders?',
  '¿Cuál es el promedio de Lead Penetration por país?',
]

// Metric columns whose values are raw ratios (0–1) and should be shown as percentages.
// Gross Profit UE is a money-like value, not a ratio — keep it as a decimal.
const NON_RATIO_COLS = new Set(['Gross Profit UE'])

// Week columns in orders table hold raw counts, not ratios.
const ORDER_WEEK_COLS = new Set(['L8W', 'L7W', 'L6W', 'L5W', 'L4W', 'L3W', 'L2W', 'L1W', 'L0W'])
const METRIC_WEEK_COLS = new Set([
  'L8W_ROLL', 'L7W_ROLL', 'L6W_ROLL', 'L5W_ROLL',
  'L4W_ROLL', 'L3W_ROLL', 'L2W_ROLL', 'L1W_ROLL', 'L0W_ROLL',
])

function formatCell(col, val, row) {
  if (val === null || val === undefined) return '—'
  if (typeof val !== 'number') return val

  // Integer-like values (order counts, IDs) → plain integer
  if (Number.isInteger(val)) return val.toLocaleString()

  // Order week columns are raw counts, not ratios
  if (ORDER_WEEK_COLS.has(col)) return val.toLocaleString(undefined, { maximumFractionDigits: 0 })

  // Metric week columns: check if the row's METRIC is a non-ratio type
  if (METRIC_WEEK_COLS.has(col)) {
    if (NON_RATIO_COLS.has(row.METRIC)) return val.toFixed(4)
    return `${(val * 100).toFixed(1)}%`
  }

  // Standalone value/group_mean columns from insights-style queries
  if ((col === 'value' || col === 'group_mean') && !NON_RATIO_COLS.has(row.METRIC)) {
    if (val > 0 && val <= 1) return `${(val * 100).toFixed(1)}%`
  }

  // Single metric value columns (L0W_ROLL used in aggregations, etc.)
  // Heuristic: if the value is between 0 and 1 exclusive and the column looks like a metric result
  if (val > 0 && val < 1 && (col.includes('AVG') || col.includes('avg') || col === 'L0W_ROLL')) {
    return `${(val * 100).toFixed(1)}%`
  }

  return val.toFixed(4)
}

function DataTable({ data }) {
  if (!data || data.length === 0) return null
  const cols = Object.keys(data[0])
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {cols.map(c => <th key={c}>{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i}>
              {cols.map(c => (
                <td key={c}>{formatCell(c, row[c], row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setError(null)
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)

    try {
      const res = await sendMessage(text, sessionId)
      setSessionId(res.session_id)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: res.answer, data: res.data, sql: res.sql },
      ])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleSuggestion(text) {
    setInput(text)
    textareaRef.current?.focus()
  }

  return (
    <div className="chat">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p className="chat-empty-title">Pregunta lo que quieras sobre metricas operacionales</p>
            <div className="chat-suggestions">
              {SUGGESTIONS.map(s => (
                <button key={s} className="suggestion-btn" onClick={() => handleSuggestion(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message message-${msg.role}`}>
            <div className="message-bubble">
              {msg.role === 'assistant' ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                <p>{msg.content}</p>
              )}
              {msg.data && msg.data.length > 0 && <DataTable data={msg.data} />}
              {msg.sql && (
                <details className="sql-details">
                  <summary>SQL</summary>
                  <pre><code>{msg.sql}</code></pre>
                </details>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="message message-assistant">
            <div className="message-bubble thinking">
              <span /><span /><span />
            </div>
          </div>
        )}

        {error && <div className="chat-error">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-bar">
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Pregunta sobre metricas operacionales... (Enter para enviar, Shift+Enter para nueva linea)"
          rows={1}
          disabled={loading}
        />
        <button
          className="chat-send"
          onClick={handleSend}
          disabled={!input.trim() || loading}
        >
          Enviar
        </button>
      </div>
    </div>
  )
}
