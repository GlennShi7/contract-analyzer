import { useState } from 'react'
import Upload from './components/Upload'
import RiskReport from './components/RiskReport'
import ContractQuestions from './components/ContractQuestions'

function App() {
  const [document, setDocument] = useState(null)

  return (
    <div>
      <h1>合同防踩坑工具</h1>
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
