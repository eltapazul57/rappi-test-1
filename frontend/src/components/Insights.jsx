import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { generateInsights } from '../api'

export default function Insights() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleGenerate() {
    setLoading(true)
    setError(null)
    try {
      const res = await generateInsights()
      setReport(res.report)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="insights">
      <div className="insights-header">
        <div>
          <h2>Informe semanal de insights</h2>
          <p>Analisis automatico de anomalias, tendencias, benchmarks y correlaciones en todas las zonas.</p>
        </div>
        <button className="insights-btn" onClick={handleGenerate} disabled={loading}>
          {loading ? 'Generando...' : report ? 'Regenerar' : 'Generar informe'}
        </button>
      </div>

      {error && <div className="chat-error">{error}</div>}

      {!report && !loading && (
        <div className="insights-empty">
          <p>Haz clic en "Generar informe" para ejecutar el analisis automatico.</p>
          <ul>
            <li>Zonas con mas del 10% de cambio semana a semana</li>
            <li>Metricas en declive durante 3 o mas semanas consecutivas</li>
            <li>Zonas con bajo rendimiento respecto a su grupo de referencia</li>
            <li>Correlaciones entre metricas</li>
          </ul>
        </div>
      )}

      {report && (
        <div className="insights-report">
          <ReactMarkdown>{report}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}
