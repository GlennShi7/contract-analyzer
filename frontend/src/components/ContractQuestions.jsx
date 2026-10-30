import { useEffect, useRef, useState } from 'react'
import './ContractQuestions.css'
import Icon from './Icon'

const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

function ContractQuestions({ docId }) {
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [turns, setTurns] = useState([])
  const questionInput = useRef(null)
  const pendingRequest = useRef(null)
  const nextTurnId = useRef(0)

  useEffect(() => () => {
    pendingRequest.current?.abort()
    pendingRequest.current = null
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()
    const submittedQuestion = question.trim()
    if (!submittedQuestion || pendingRequest.current) return
    const controller = new AbortController()
    const turnId = ++nextTurnId.current
    pendingRequest.current = controller
    setAsking(true)
    setTurns(previous => [...previous, { id: turnId, question: submittedQuestion, status: 'pending' }])
    setQuestion('')
    try {
      const response = await fetch(`${apiUrl}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: docId, question: submittedQuestion }),
        signal: controller.signal,
      })
      let data
      try {
        data = await response.json()
      } catch {
        throw new Error('无法读取问答结果，请稍后重试。')
      }
      if (!data || typeof data !== 'object') throw new Error('问答结果格式不完整，请稍后重试。')
      if (!response.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : '问答失败，请稍后重试。')
      }
      if (data.doc_id !== docId || !Array.isArray(data.sources) || data.sources.length === 0 ||
          data.sources.some(source => !source || source.doc_id !== docId || !Number.isInteger(source.chunk) || source.chunk < 0 ||
            typeof source.text !== 'string' || !source.text.trim())) {
        throw new Error('回答与当前合同的对应信息不完整，请重新上传后再试。')
      }
      if (typeof data.answer !== 'string' || !data.answer.trim()) {
        throw new Error('未收到有效回答，请稍后重试。')
      }
      if (!controller.signal.aborted) {
        setTurns(previous => previous.map(turn => turn.id === turnId ?
          { ...turn, status: 'complete', answer: data.answer, sources: data.sources } : turn))
      }
    } catch (err) {
      if (!controller.signal.aborted) {
        const message = err instanceof TypeError ? '无法连接问答服务，请检查后端是否启动。' : err.message || '问答失败，请稍后重试。'
        setTurns(previous => previous.map(turn => turn.id === turnId ? { ...turn, status: 'error', error: message } : turn))
      }
    } finally {
      if (pendingRequest.current === controller) {
        pendingRequest.current = null
        setAsking(false)
      }
    }
  }

  return (
    <section className="contract-questions panel" aria-labelledby="contract-questions-title">
      <div className="section-heading"><span className="section-number">03</span><h2 id="contract-questions-title">问问这份合同</h2></div>
      <p className="section-description">可以询问押金、付款期限、维修等合同约定。每次问题独立回答，追问请补全指代。</p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="contract-question">你的问题</label>
        <textarea ref={questionInput} id="contract-question" value={question} onChange={event => setQuestion(event.target.value)}
          placeholder="这份合同约定，搬出后多久退还押金？" maxLength={4000} disabled={asking} required />
        <div className="question-form-footer"><span>答案附原文片段，可展开核对</span><button className="primary-button" type="submit" disabled={!question.trim() || asking}>{asking ? '正在查阅合同…' : '提问'}<Icon name="arrow" size={16} /></button></div>
      </form>
      <div className="question-suggestions"><span>可以这样问</span>{['押金多久退还？', '会自动续租吗？'].map(value => <button key={value} type="button" disabled={asking}
        onClick={() => { setQuestion(value); questionInput.current?.focus() }}>{value}</button>)}</div>
      {turns.length > 0 && (
        <button type="button" className="clear-questions" disabled={asking}
          onClick={() => { setTurns([]); setQuestion('') }}>清空本页问答</button>
      )}
      <ol className="question-history" aria-label="本页问答记录" aria-live="polite">
        {turns.map((turn, index) => (
          <li key={turn.id} data-qa-status={turn.status}>
            <article aria-label={turn.status === 'complete' ? '合同问答结果' : '合同问答记录'}>
              <h3><span className="question-index">{String(index + 1).padStart(2, '0')}</span>{turn.question}</h3>
              {turn.status === 'pending' && <p role="status">正在查找相关约定并生成回答…</p>}
              {turn.status === 'error' && <p className="error-message" role="alert">{turn.error}</p>}
              {turn.status === 'complete' && (
                <>
                  <p className="contract-answer">{turn.answer}</p>
                  <h4>核对合同原文</h4>
                  <p>这些是本次检索到的片段，仍需核对它们是否支持回答；片段可能未包含完整条款和例外。</p>
                  {turn.sources.map((source, sourceIndex) => (
                    <details className="source-details" key={`${source.doc_id}-${source.chunk}`}>
                      <summary>合同原文{sourceIndex + 1}</summary>
                      <blockquote>{source.text}</blockquote>
                    </details>
                  ))}
                </>
              )}
            </article>
          </li>
        ))}
      </ol>
      <p className="contract-questions-note">问答用于理解当前合同，不判断条款法律效力。记录仅保留在本页，刷新或切换文件会清除；清空记录不删除服务端合同。</p>
    </section>
  )
}

export default ContractQuestions
