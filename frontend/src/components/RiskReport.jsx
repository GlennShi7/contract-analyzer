import { useEffect, useRef, useState } from 'react'
import Icon from './Icon'
import { useLanguage } from '../language'
import ErrorMessage from './ErrorMessage'
import { isRenderableReport } from '../report'

const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const replayDemo = import.meta.env.VITE_REPLAY_DEMO === 'true'
const riskLabels = { high: '高风险', medium: '中风险', low: '低风险' }
const lawLevels = { national: '国家法律', municipal: 'Urbana 市条例', state: '伊利诺伊州法', federal: '美国联邦法' }
// "illegal" is the label reports used before Nov 2026 for the same finding.
const categoryLabels = { conflict: '与条文不一致', illegal: '与条文不一致', risk: '风险', verify: '待核实', missing: '缺失' }
// Problems every tenant meets come first; the backend already sorts cards in this order.
const tierGroups = [['universal', '每个人都会碰上'], ['common', '常见情况'], ['rare', '少见情况'], [null, '清单之外']]

function groupCards(cards) {
  if (!cards.some(card => card.tier)) return [[null, null, cards]]
  return tierGroups.map(([tier, label]) => [tier, label, cards.filter(card => (card.tier || null) === tier)]).filter(([, , items]) => items.length)
}

function RiskReport({ docId }) {
  const { t, language } = useLanguage()
  const [report, setReport] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [jurisdiction, setJurisdiction] = useState('unknown')
  const [pipeline, setPipeline] = useState('single')
  const pendingRequest = useRef(null)

  useEffect(() => () => {
    pendingRequest.current?.abort()
    pendingRequest.current = null
  }, [])

  const laws = new Map((report?.legal_sources || []).map(law => [law.id, law]))

  function handleJurisdictionChange(e) {
    setJurisdiction(e.target.value)
    setReport(null)
    setError('')
  }

  function handlePipelineChange(e) {
    setPipeline(e.target.value)
    setReport(null)
    setError('')
  }

  async function handleAnalyze() {
    if (!docId || pendingRequest.current) return
    const controller = new AbortController()
    pendingRequest.current = controller
    setAnalyzing(true)
    setError('')
    setReport(null)
    try {
      const res = await fetch(`${apiUrl}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // The report is written in the interface language; quoted clauses stay in the contract's language.
        body: JSON.stringify({ doc_id: docId, jurisdiction, output_language: language, pipeline }),
        signal: controller.signal,
      })
      let data
      try {
        data = await res.json()
      } catch {
        throw new Error('无法读取分析结果，请稍后重试。')
      }
      if (!res.ok) {
        throw new Error(typeof data?.detail === 'string' ? data.detail : '分析失败，请重试')
      }
      if (data?.doc_id !== docId) {
        throw new Error('分析结果与当前合同不对应，请重新上传后再试。')
      }
      if (!isRenderableReport(data.result)) {
        throw new Error('分析结果格式不完整，请稍后重试。')
      }
      if (!controller.signal.aborted) setReport(data.result)
    } catch (err) {
      if (!controller.signal.aborted) setError(err.message || '分析失败，请检查后端连接')
    } finally {
      if (pendingRequest.current === controller) {
        pendingRequest.current = null
        setAnalyzing(false)
      }
    }
  }

  return (
    <section className="risk-panel panel" aria-labelledby="risk-panel-title">
      <div className="section-heading"><span className="section-number">02</span><h2 id="risk-panel-title">{t("核对合同风险")}</h2></div>
      <p className="section-description">{t("确认地区后，逐项查看合同约定、解释和法条来源。")}</p>
      <div className="analysis-toolbar">
        <label className="region-control">{t("合同适用地区：")}<select value={jurisdiction} onChange={handleJurisdictionChange} disabled={analyzing}>
            <option value="unknown">{t("其他 / 不确定")}</option>
            <option value="cn">{t("中国大陆")}</option>
            <option value="us_il_urbana">{t("美国 · Urbana, Illinois")}</option>
            <option value="us_il">{t("美国 · 伊利诺伊州（Urbana 以外，如 Champaign）")}</option>
          </select>
        </label>
        <label className="region-control">{t("分析方式：")}<select value={pipeline} onChange={handlePipelineChange} disabled={analyzing}>
            <option value="single">{t("一次分析整份合同")}</option>
            <option value="per_item">{t("逐项检查（新，约 40 次调用）")}</option>
          </select>
        </label>
        <button className="primary-button" onClick={handleAnalyze} disabled={!docId || analyzing}>
          {analyzing ? t("分析中...") : t("分析风险")}<Icon name="arrow" size={16} />
        </button>
      </div>
      <p className="scope-hint">{t(jurisdiction === 'us_il_urbana' ? "选 Urbana 即视为房子在 Urbana 市界内，报告会据此判断是否违反市条例。Urbana 不包括 Champaign 或 Chicago；不确定时选“其他 / 不确定”。" : jurisdiction === 'us_il' ? "只用伊利诺伊州法和联邦法；Champaign、Chicago 等城市条例未收录。房子在 Urbana 请选上一项。" : jurisdiction === 'cn' ? "中国大陆法律参考；具体地域、时间和条文适用条件仍需核实。" : "未注入适用法律，仅提供合同文字风险提示。")}</p>
      {error && <ErrorMessage message={error} fallback="分析失败，请重试" />}
      {!report && !error && <div className="analysis-empty" role={analyzing ? 'status' : undefined}>
        <span className="soft-icon"><Icon name="search" size={22} /></span>
        <div><strong>{analyzing ? t("正在逐项阅读这份合同…") : t("准备好后，开始第一轮核对")}</strong><p>{analyzing ? t("分析需要一些时间，请保持当前页面。") : t("结果将展示原文、风险解释与可展开的法条来源。")}</p></div>
      </div>}
      {report && (
        <section aria-label={t("合同风险报告")}>
          <div className="report-header">
            <div className="score-tile" aria-label={t("风险提示评分：{score}/10", { score: report.risk_score })}>
              <h3>{t("风险提示评分")}</h3><p className="score-value">{report.risk_score}<span>/ 10</span></p><small>{t("提示性评分，不是法律结论")}</small>
            </div>
            <div className="report-summary"><h2>{t("这份合同，需要关注什么？")}</h2><p className="content-language-note">{t(replayDemo ? "报告、回答和引用原文保留原有语言。" : "报告和回答使用生成时的界面语言；引用的合同原文保持原文语言。")}</p><p>{report.summary}</p>
              {report.grounding?.cards_dropped > 0 && <p className="dropped-note"><Icon name="info" size={13} />{t("有 {count} 张卡片没通过检查（格式不对，或引用的原文在合同里找不到），已去掉；这些清单项请自己对照合同核实。", { count: report.grounding.cards_dropped })}</p>}
              {report.grounding?.truncated && <p className="dropped-note"><Icon name="info" size={13} />{t("模型输出太长，中途被截断；报告保留了截断前写完整的卡片，后面的清单项可能没检查到，请对照清单自己核实。")}</p>}
              {report.grounding?.cards_capped > 0 && <p className="dropped-note"><Icon name="info" size={13} />{t("同一清单项最多保留 3 张卡，另外 {count} 张（多是收费表逐行出的卡）已去掉。", { count: report.grounding.cards_capped })}</p>}
              {report.grounding?.items_failed?.length > 0 && <p className="dropped-note"><Icon name="info" size={13} />{t("第 {items} 项没能完成检查，请对照清单自己核实。", { items: report.grounding.items_failed.join('、') })}</p>}
              {report.grounding?.pipeline === 'per_item' && <p className="content-language-note">{t("逐项检查：{judged} 项交给模型判断，共 {calls} 次调用；风险评分按卡片类别用固定公式计算。", { judged: Object.values(report.grounding.item_verdicts || {}).filter(v => !['missing', 'not_found'].includes(v)).length, calls: report.grounding.calls })}</p>}
              <details className="scope-details"><summary>{t("本次法条范围与适用条件")}</summary><p>{t(report.legal_scope)}</p></details>
            </div>
          </div>
          <div className="risk-list-heading"><h3>{t("逐项核对")}<span>{t("· {count} 项提示", { count: report.cards.length })}</span></h3><span>{t("结合原文与实际情况阅读")}</span></div>
          {report.cards.length === 0 && <p className="scope-hint">{t("本次未列出风险卡片，不代表合同不存在风险。")}</p>}
          {groupCards(report.cards).map(([tier, label, cards]) => (
            <div key={tier || 'other'} className="risk-group">
              {label && <h4 className="risk-group-heading">{t(label)}<span>{t("{count} 项", { count: cards.length })}</span></h4>}
              {cards.map((card, index) => (
            <article key={index} className={`risk-card risk-${card.risk_level}${card.category ? ` category-${card.category}` : ''}`}>
              <div className="risk-card-heading"><span className="risk-badge">{t(card.category ? categoryLabels[card.category] : riskLabels[card.risk_level])}</span><h3>{card.title}</h3></div>
              {card.checklist_item && <p className="checklist-label">{t("清单第 {n} 项", { n: card.checklist_item })}{card.checklist_name ? ` · ${card.checklist_name}` : ''}{card.also_items?.length > 0 ? ` · ${t("也涉及第 {items} 项", { items: card.also_items.join('、') })}` : ''}{card.pages?.length > 0 ? ` · ${t("第 {pages} 页", { pages: card.pages.join('–') })}` : ''}</p>}
              {card.category === 'missing' ? (
                <p className="quote-status missing"><Icon name="info" size={13} />{t("租约里没有找到这项约定")}</p>
              ) : (
                <>
                  <blockquote className="clause-quote">{card.clause_text}</blockquote>
                  <p className={`quote-status${card.verified ? '' : ' unverified'}`}><Icon name={card.verified ? 'check' : 'info'} size={13} />{card.verified ? t("引用已匹配合同原文") : t("引用未逐字匹配，请回到合同核对")}</p>
                </>
              )}
              {card.category_downgraded && <p className="downgrade-note">{t("模型标为与条文不一致，但没有可核对的法条，已改为待核实。")}</p>}
              <p className="risk-explanation">{card.explanation}</p>
              <p className="risk-suggestion"><strong>{t("建议：")}</strong>{card.suggestion}</p>
              {card.legal_basis.length === 0 && <p className="no-law">{t("暂无可核对的法条依据。")}</p>}
              {card.legal_basis.length > 0 && <p className="law-heading">{t("法条依据 · 展开核对适用条件")}</p>}
              {card.legal_basis.map(id => {
                const law = laws.get(id)
                return law && (
                  <details key={id} className="source-details">
                    <summary>{law.law} {law.article}</summary>
                    <div className="source-details-body"><span className="law-level">{t(lawLevels[law.authority_level] || "法律条文")}</span>
                      <p className="source-text">{law.text}</p>
                      {law.applicability && <p>{t("适用条件：")}{law.applicability}</p>}
                      <a href={law.source_url} target="_blank" rel="noreferrer">{t("查看官方原文 ↗")}</a>
                      <p>{t("来源核对日期：")}{law.checked_on}</p>
                    </div>
                  </details>
                )
              })}
            </article>
              ))}
            </div>
          ))}
          <p className="report-disclaimer"><Icon name="info" size={15} />{t(report.disclaimer)}</p>
        </section>
      )}
    </section>
  )
}

export default RiskReport
