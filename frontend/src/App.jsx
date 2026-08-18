import { useState } from 'react'
import Upload from './components/Upload'
import RiskReport from './components/RiskReport'

function App() {
  const [contractText, setContractText] = useState('')

  return (
    <div>
      <h1>合同防踩坑工具</h1>
      <Upload onTextExtracted={setContractText} />
      <RiskReport contractText={contractText} />
      <p>已提取字数：{contractText.length}</p>
    </div>
  )
}

export default App
