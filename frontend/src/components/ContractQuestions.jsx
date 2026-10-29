import { useEffect, useRef, useState } from 'react'
import './ContractQuestions.css'

const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

function ContractQuestions({ docId }) {
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const pendingRequest = useRef(null)

  useEffect(() => () => {
    pendingRequest.current?.abort()
    pendingRequest.current = null
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()
    const submittedQuestion = question.trim()
    if (!submittedQuestion || pendingRequest.current) return
    const controller = new AbortController()
    pendingRequest.current = controller
    setAsking(true)
    setError('')
    setResult(null)
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
      if (!controller.signal.aborted) setResult({ ...data, question: submittedQuestion })
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(err instanceof TypeError ? '无法连接问答服务，请检查后端是否启动。' : err.message || '问答失败，请稍后重试。')
      }
    } finally {
      if (pendingRequest.current === controller) {
        pendingRequest.current = null
        setAsking(false)
      }
    }
  }

  return (
    <section className="contract-questions" aria-labelledby="contract-questions-title">
      <h2 id="contract-questions-title">问问这份合同</h2>
      <p>可以询问押金、付款期限、维修等合同约定。每次请写清问题，回答后请核对合同原文。</p>
      <form onSubmit={handleSubmit}>
        <label htmlFor="contract-question">你的问题</label>
        <textarea id="contract-question" value={question} onChange={event => setQuestion(event.target.value)}
          placeholder="这份合同约定，搬出后多久退还押金？" maxLength={4000} disabled={asking} required />
        <button type="submit" disabled={!question.trim() || asking}>{asking ? '正在查阅合同…' : '提问'}</button>
      </form>
      {asking && <p role="status">正在查找相关约定并生成回答…</p>}
      {error && <p role="alert">{error}</p>}
      <div aria-live="polite">
        {result && (
          <article aria-label="合同问答结果">
            <h3>问题：{result.question}</h3>
            <p className="contract-answer">{result.answer}</p>
            <h3>核对合同原文</h3>
            <p>这些是本次检索到的片段，仍需核对它们是否支持回答；片段可能未包含完整条款和例外。</p>
            {result.sources.map((source, index) => (
              <details key={`${source.doc_id}-${source.chunk}`}>
                <summary>合同原文{index + 1}</summary>
                <blockquote>{source.text}</blockquote>
              </details>
            ))}
          </article>
        )}
      </div>
      <p className="contract-questions-note">问答用于理解当前合同，不判断条款法律效力。切换文件会清除当前问题和回答。</p>
    </section>
  )
}

export default ContractQuestions
