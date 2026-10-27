import { useState } from 'react'

const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

function RiskReport({ docId }) {
  const [report, setReport] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')

  async function handleAnalyze() {
    setAnalyzing(true)
    setError('')
    setReport('')
    try {
      const res = await fetch(`${apiUrl}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : '分析失败，请重试')
      }
      setReport(data.result)
    } catch (err) {
      setError(err.message || '分析失败，请检查后端连接')
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div>
      <button onClick={handleAnalyze} disabled={!docId || analyzing}>
        {analyzing ? '分析中...' : '分析风险'}
      </button>
      {error && <p role="alert">{error}</p>}
      {report && <p style={{ whiteSpace: 'pre-wrap' }}>{report}</p>}
    </div>
  )
}

export default RiskReport
