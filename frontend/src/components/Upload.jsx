import { useState } from 'react'

const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

function Upload({ onUploaded }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState('')
  const [error, setError] = useState('')

  function handleFileChange(e) {
    setSelectedFile(e.target.files[0] || null)
    setPreview('')
    setError('')
    onUploaded(null)
  }

  async function handleUpload() {
    const formData = new FormData()
    formData.append('file', selectedFile)
    setUploading(true)
    setError('')
    setPreview('')
    onUploaded(null)
    try {
      const res = await fetch(`${apiUrl}/upload`, { method: 'POST', body: formData })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : '上传失败，请重试')
      }
      setPreview(data.preview)
      onUploaded(data)
    } catch (err) {
      setError(err.message || '上传失败，请检查后端连接')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div>
      <input type="file" accept=".pdf" onChange={handleFileChange} disabled={uploading} />
      {selectedFile && <p>已选择：{selectedFile.name}</p>}
      <button onClick={handleUpload} disabled={!selectedFile || uploading}>
        {uploading ? '上传中...' : '上传'}
      </button>
      {error && <p role="alert">{error}</p>}
      {preview && <p>{preview}</p>}
    </div>
  )
}

export default Upload
