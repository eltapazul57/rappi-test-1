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
          <h2>Weekly Insights Report</h2>
          <p>Automated analysis of anomalies, trends, benchmarks, and correlations across all zones.</p>
        </div>
        <button className="insights-btn" onClick={handleGenerate} disabled={loading}>
          {loading ? 'Generating…' : report ? 'Regenerate' : 'Generate Report'}
        </button>
      </div>

      {error && <div className="chat-error">{error}</div>}

      {!report && !loading && (
        <div className="insights-empty">
          <p>Click "Generate Report" to run the automated analysis.</p>
          <ul>
            <li>Zones with &gt;10% week-over-week change</li>
            <li>Metrics declining 3+ consecutive weeks</li>
            <li>Zones underperforming vs their peer group</li>
            <li>Correlations between metrics</li>
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
