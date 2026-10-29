import { useState } from 'react'
import Upload from './components/Upload'
import RiskReport from './components/RiskReport'
import ContractQuestions from './components/ContractQuestions'
import './DemoNotice.css'

const replayDemo = import.meta.env.VITE_REPLAY_DEMO === 'true'

function App() {
  const [document, setDocument] = useState(null)

  return (
    <div>
      <h1>合同防踩坑工具</h1>
      {replayDemo && (
        <aside className="demo-notice" aria-label="回放演示说明">
          <strong>回放演示 · 不调用付费 API</strong>
          <p>风险分析回放2026年10月28日保存的结果，含已知解释偏差；问答为预设示例，不是新生成结果。</p>
          <p><a href="/demo/lease_en.pdf" download>下载合成演示 PDF</a>，上传后选择“美国 · Urbana, Illinois”。此模式仅接受该样例。</p>
          <p>可试问：“押金多久退还？”或“会自动续租吗？”</p>
        </aside>
      )}
      <Upload onUploaded={setDocument} />
      {document && (
        <>
          <p>已上传：{document.filename}，共 {document.n_chunks} 个检索片段</p>
          <RiskReport key={`risk-${document.doc_id}`} docId={document.doc_id} />
          <ContractQuestions key={`questions-${document.doc_id}`} docId={document.doc_id} />
        </>
      )}
    </div>
  )
}

export default App
