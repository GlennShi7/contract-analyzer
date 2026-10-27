import { useState } from 'react'

const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险' }
const riskColors = { high: '#b42318', medium: '#9a6700', low: '#175cd3' }

function RiskReport({ docId }) {
  const [report, setReport] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [jurisdiction, setJurisdiction] = useState('unknown')
  const laws = new Map((report?.legal_sources || []).map(law => [law.id, law]))

  function handleJurisdictionChange(e) {
    setJurisdiction(e.target.value)
    setReport(null)
    setError('')
  }

  async function handleAnalyze() {
    setAnalyzing(true)
    setError('')
    setReport(null)
    try {
      const res = await fetch(`${apiUrl}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId, jurisdiction }),
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
    <div style={{ textAlign: 'left', maxWidth: '52rem', margin: '2rem auto' }}>
      <p>
        <label>
          合同适用地区：
          <select value={jurisdiction} onChange={handleJurisdictionChange} disabled={analyzing}>
            <option value="unknown">其他 / 不确定</option>
            <option value="cn">中国大陆</option>
          </select>
        </label>
      </p>
      <p>确认适用中国大陆法律后，可查看对应法条参考；不确定时先分析合同文字风险。</p>
      <button onClick={handleAnalyze} disabled={!docId || analyzing}>
        {analyzing ? '分析中...' : '分析风险'}
      </button>
      {error && <p role="alert">{error}</p>}
      {report && (
        <section aria-label="合同风险报告">
          <h2>风险提示评分：{report.risk_score}/10</h2>
          <p style={{ whiteSpace: 'pre-wrap' }}>{report.summary}</p>
          <p>{report.legal_scope}</p>
          {report.cards.length === 0 && <p>本次未列出风险卡片，不代表合同不存在风险。</p>}
          {report.cards.map((card, index) => (
            <article key={index} style={{ borderLeft: `4px solid ${riskColors[card.risk_level]}`, paddingLeft: '1rem', margin: '1.5rem 0' }}>
              <h3>{riskLabels[card.risk_level]} · {card.title}</h3>
              <blockquote style={{ whiteSpace: 'pre-wrap', margin: '0.75rem 0', padding: '0.75rem', background: 'rgba(127, 127, 127, 0.1)' }}>{card.clause_text}</blockquote>
              <p>{card.verified ? '引用已匹配合同原文' : '引用未逐字匹配，请回到合同核对'}</p>
              <p>{card.explanation}</p>
              <p><strong>建议：</strong>{card.suggestion}</p>
              {card.legal_basis.length === 0 && <p>暂无可核对的法条依据。</p>}
              {card.legal_basis.map(id => {
                const law = laws.get(id)
                return law && (
                  <details key={id}>
                    <summary>{law.law} {law.article}</summary>
                    <p style={{ whiteSpace: 'pre-wrap' }}>{law.text}</p>
                    <a href={law.source_url} target="_blank" rel="noreferrer">查看官方原文</a>
                    <p>来源核对日期：{law.checked_on}</p>
                  </details>
                )
              })}
            </article>
          ))}
          <p>{report.disclaimer}</p>
        </section>
      )}
    </div>
  )
}

export default RiskReport
