import { useState } from 'react'

function RiskReport({ contractText }) {
  const [report, setReport] = useState('')
  const [analyzing, setAnalyzing] = useState(false)

  async function handleAnalyze() {
    setAnalyzing(true)
    try {
      const res = await fetch('http://127.0.0.1:8000/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: contractText }),
      })
      const data = await res.json()
      setReport(data.result)
    } catch (err) {
      console.error(err)
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div>
      <button onClick={handleAnalyze} disabled={!contractText || analyzing}>
        {analyzing ? '分析中...' : '分析风险'}
      </button>

      {report && <p style={{ whiteSpace: 'pre-wrap' }}>{report}</p>}
    </div>
  )
}

export default RiskReport