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
              {cols.map(c => {
                const val = row[c]
                const formatted =
                  typeof val === 'number'
                    ? Number.isInteger(val) ? val : val.toFixed(4)
                    : val ?? '—'
                return <td key={c}>{formatted}</td>
              })}
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
            <p className="chat-empty-title">Ask anything about operational metrics</p>
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
          placeholder="Ask about operational metrics… (Enter to send, Shift+Enter for new line)"
          rows={1}
          disabled={loading}
        />
        <button
          className="chat-send"
          onClick={handleSend}
          disabled={!input.trim() || loading}
        >
          Send
        </button>
      </div>
    </div>
  )
}
