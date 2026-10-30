import { useState } from 'react'
import Icon from './Icon'

const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险' }
const lawLevels = { national: '国家法律', municipal: 'Urbana 市条例', state: '伊利诺伊州法', federal: '美国联邦法' }

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
    <section className="risk-panel panel" aria-labelledby="risk-panel-title">
      <div className="section-heading"><span className="section-number">02</span><h2 id="risk-panel-title">核对合同风险</h2></div>
      <p className="section-description">确认地区后，逐项查看合同约定、解释和法条来源。</p>
      <div className="analysis-toolbar">
        <label className="region-control">合同适用地区：
          <select value={jurisdiction} onChange={handleJurisdictionChange} disabled={analyzing}>
            <option value="unknown">其他 / 不确定</option>
            <option value="cn">中国大陆</option>
            <option value="us_il_urbana">美国 · Urbana, Illinois</option>
          </select>
        </label>
        <button className="primary-button" onClick={handleAnalyze} disabled={!docId || analyzing}>
          {analyzing ? '分析中...' : '分析风险'}<Icon name="arrow" size={16} />
        </button>
      </div>
      <p className="scope-hint">Urbana 不包括 Champaign 或 Chicago；不确定地区时，先查看文字风险。</p>
      {error && <p className="error-message" role="alert">{error}</p>}
      {!report && !error && <div className="analysis-empty" role={analyzing ? 'status' : undefined}>
        <span className="soft-icon"><Icon name="search" size={22} /></span>
        <div><strong>{analyzing ? '正在逐项阅读这份合同…' : '准备好后，开始第一轮核对'}</strong><p>{analyzing ? '分析需要一些时间，请保持当前页面。' : '结果将展示原文、风险解释与可展开的法条来源。'}</p></div>
      </div>}
      {report && (
        <section aria-label="合同风险报告">
          <div className="report-header">
            <div className="score-tile" aria-label={`风险提示评分：${report.risk_score}/10`}>
              <h3>风险提示评分</h3><p className="score-value">{report.risk_score}<span>/ 10</span></p><small>提示性评分，非违法概率</small>
            </div>
            <div className="report-summary"><h2>这份合同，需要关注什么？</h2><p>{report.summary}</p>
              <details className="scope-details"><summary>本次法条范围与适用条件</summary><p>{report.legal_scope}</p></details>
            </div>
          </div>
          <div className="risk-list-heading"><h3>逐项核对 <span>· {report.cards.length} 项提示</span></h3><span>结合原文与实际情况阅读</span></div>
          {report.cards.length === 0 && <p className="scope-hint">本次未列出风险卡片，不代表合同不存在风险。</p>}
          {report.cards.map((card, index) => (
            <article key={index} className={`risk-card risk-${card.risk_level}`}>
              <div className="risk-card-heading"><span className="risk-badge">{riskLabels[card.risk_level]}</span><h3>{card.title}</h3></div>
              <blockquote className="clause-quote">{card.clause_text}</blockquote>
              <p className={`quote-status${card.verified ? '' : ' unverified'}`}><Icon name={card.verified ? 'check' : 'info'} size={13} />{card.verified ? '引用已匹配合同原文' : '引用未逐字匹配，请回到合同核对'}</p>
              <p className="risk-explanation">{card.explanation}</p>
              <p className="risk-suggestion"><strong>建议：</strong>{card.suggestion}</p>
              {card.legal_basis.length === 0 && <p className="no-law">暂无可核对的法条依据。</p>}
              {card.legal_basis.length > 0 && <p className="law-heading">法条依据 · 展开核对适用条件</p>}
              {card.legal_basis.map(id => {
                const law = laws.get(id)
                return law && (
                  <details key={id} className="source-details">
                    <summary>{law.law} {law.article}</summary>
                    <div className="source-details-body"><span className="law-level">{lawLevels[law.authority_level] || '法律条文'}</span>
                      <p className="source-text">{law.text}</p>
                      {law.applicability && <p>适用条件：{law.applicability}</p>}
                      <a href={law.source_url} target="_blank" rel="noreferrer">查看官方原文 ↗</a>
                      <p>来源核对日期：{law.checked_on}</p>
                    </div>
                  </details>
                )
              })}
            </article>
          ))}
          <p className="report-disclaimer"><Icon name="info" size={15} />{report.disclaimer}</p>
        </section>
      )}
    </section>
  )
}

export default RiskReport
