import { useEffect, useRef, useState } from 'react'
import Icon from './Icon'
import ErrorMessage from './ErrorMessage'
import { useLanguage } from '../language'
import { isRenderableRetrieval } from '../report'

const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const statusLabels = { found: '找到相关条款', absent: '可能没写', no_match: '没有匹配' }
const tierLabels = { universal: '每个人都会碰上', common: '常见情况', rare: '少见情况' }
const escapeRegExp = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// Mark keyword hits the way the backend matched them: case-insensitive, at the start of a word.
function highlight(text, keywords) {
  if (!keywords.length) return text
  const pattern = new RegExp(`\\b(${keywords.map(escapeRegExp).sort((a, b) => b.length - a.length).join('|')})`, 'gi')
  const parts = []
  let last = 0
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parts.push(text.slice(last, match.index))
    parts.push(<mark key={match.index}>{match[0]}</mark>)
    last = match.index + match[0].length
  }
  parts.push(text.slice(last))
  return parts
}

function RetrievalPreview({ docId }) {
  const { t, language } = useLanguage()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const pendingRequest = useRef(null)

  useEffect(() => () => {
    pendingRequest.current?.abort()
    pendingRequest.current = null
  }, [])

  async function handleRetrieve() {
    if (!docId || pendingRequest.current) return
    const controller = new AbortController()
    pendingRequest.current = controller
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await fetch(`${apiUrl}/retrieve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId }),
        signal: controller.signal,
      })
      let data
      try {
        data = await res.json()
      } catch {
        throw new Error('无法读取检索结果，请稍后重试。')
      }
      if (!res.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : '检索失败，请重试')
      if (data?.doc_id !== docId) throw new Error('检索结果与当前合同不对应，请重新上传后再试。')
      if (!isRenderableRetrieval(data)) throw new Error('检索结果格式不完整，请稍后重试。')
      if (!controller.signal.aborted) setResult(data)
    } catch (err) {
      if (!controller.signal.aborted) setError(err.message || '检索失败，请检查后端连接')
    } finally {
      if (pendingRequest.current === controller) {
        pendingRequest.current = null
        setLoading(false)
      }
    }
  }

  const counts = result ? Object.fromEntries(Object.keys(statusLabels).map(status => [status, result.items.filter(item => item.status === status).length])) : {}

  return (
    <section className="retrieval-panel panel" aria-labelledby="retrieval-panel-title">
      <div className="section-heading"><span className="section-number">02b</span><h2 id="retrieval-panel-title">{t("逐项检索预览")}</h2></div>
      <p className="section-description">{t("不调用模型：把合同切成条款，按清单 43 项各找出最相关的几段。新版逐项检查会只拿这些段去判断，所以这里漏掉的条款，后面也看不到。")}</p>
      <div className="analysis-toolbar">
        <button className="primary-button" onClick={handleRetrieve} disabled={!docId || loading}>
          {loading ? t("检索中...") : t("查看每项检索到的条款")}<Icon name="search" size={16} />
        </button>
      </div>
      {error && <ErrorMessage message={error} fallback="检索失败，请重试" />}
      {result && (
        <div className="retrieval-result">
          <p className="retrieval-summary">{t("切成 {segments} 段；{found} 项找到相关条款，{absent} 项可能没写，{none} 项没有匹配。", { segments: result.segments_total, found: counts.found, absent: counts.absent, none: counts.no_match })}</p>
          {!result.pages_known && <p className="dropped-note"><Icon name="info" size={13} />{t("这份合同是在保存页码之前上传的，所以不显示页码；重新上传同一个 PDF 即可显示。")}</p>}
          <p className="scope-hint">{t("“可能没写”只表示清单关键词一个都没出现，不代表一定缺失；黄色标出的是命中的关键词。")}</p>
          <div className="retrieval-items">
            {result.items.map(item => {
              const pages = [...new Set(item.hits.flatMap(hit => result.segments[hit.segment]?.pages || []))].sort((a, b) => a - b)
              return (
                <details key={item.id} className={`retrieval-item status-${item.status}`}>
                  <summary>
                    <span className="retrieval-item-title">{t("第 {n} 项", { n: item.id })} · {language === 'en' ? item.name_en : item.name_zh}</span>
                    <span className="retrieval-badge">{t(statusLabels[item.status] || item.status)}</span>
                    <span className="retrieval-meta">{t("{count} 段", { count: item.hits.length })}{pages.length > 0 && ` · ${t("第 {pages} 页", { pages: pages.join(', ') })}`}</span>
                  </summary>
                  <div className="retrieval-item-body">
                    <p className="checklist-label">{t(tierLabels[item.tier] || '')}</p>
                    {item.hits.length === 0 && <p className="scope-hint">{t("没有检索到任何段落。")}</p>}
                    {item.hits.map((hit, index) => {
                      const segment = result.segments[hit.segment]
                      if (!segment) return null
                      return (
                        <article key={hit.segment} className="retrieval-hit">
                          <p className="retrieval-hit-meta">
                            <strong>#{index + 1}</strong>
                            {segment.pages.length > 0 && <span>{t("第 {pages} 页", { pages: segment.pages.join('–') })}</span>}
                            {(segment.heading || segment.section) && <span>{segment.heading || `${segment.section} ${t("（续）")}`}</span>}
                            {hit.keywords.length > 0 ? hit.keywords.map(keyword => <span key={keyword} className="keyword-chip">{keyword}</span>)
                              : <span className="weak-hit">{t("无关键词命中，按词频补位")}</span>}
                          </p>
                          <blockquote className="clause-quote">{highlight(segment.text, hit.keywords)}</blockquote>
                        </article>
                      )
                    })}
                  </div>
                </details>
              )
            })}
          </div>
        </div>
      )}
    </section>
  )
}

export default RetrievalPreview
