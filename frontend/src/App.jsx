import { useState } from 'react'
import Upload from './components/Upload'
import RiskReport from './components/RiskReport'

function App() {
  const [document, setDocument] = useState(null)

  return (
    <div>
      <h1>合同防踩坑工具</h1>
      <Upload onUploaded={setDocument} />
      {document && (
        <>
          <p>已上传：{document.filename}，共 {document.n_chunks} 个检索片段</p>
          <RiskReport key={document.doc_id} docId={document.doc_id} />
        </>
      )}
    </div>
  )
}

export default App
