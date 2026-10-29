import { useRef, useState } from 'react'

const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const maxFileBytes = 20 * 1024 * 1024

function Upload({ onUploaded }) {
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState('')
  const [error, setError] = useState('')
  const pendingUpload = useRef(false)

  function handleFileChange(e) {
    const file = e.target.files[0] || null
    const oversized = file && file.size > maxFileBytes
    setSelectedFile(oversized ? null : file)
    setPreview('')
    setError(oversized ? 'PDF 文件不能超过 20 MiB，请拆分后上传。' : '')
    if (oversized) e.target.value = ''
    onUploaded(null)
  }

  async function handleUpload() {
    if (!selectedFile || pendingUpload.current) return
    pendingUpload.current = true
    const formData = new FormData()
    formData.append('file', selectedFile)
    setUploading(true)
    setError('')
    setPreview('')
    onUploaded(null)
    try {
      const res = await fetch(`${apiUrl}/upload`, { method: 'POST', body: formData })
      let data
      try {
        data = await res.json()
      } catch {
        throw new Error(res.status === 413 ? 'PDF 文件或请求过大，请拆分后上传。' : '上传服务返回了无法读取的结果，请稍后重试。')
      }
      if (!res.ok) {
        throw new Error(typeof data?.detail === 'string' ? data.detail : '上传失败，请重试')
      }
      if (!data || !/^[0-9a-f]{64}$/.test(data.doc_id) || typeof data.filename !== 'string' ||
          typeof data.preview !== 'string' || !Number.isInteger(data.n_chunks) || data.n_chunks < 1) {
        throw new Error('上传结果不完整，请重试。')
      }
      setPreview(data.preview)
      onUploaded(data)
    } catch (err) {
      setError(err instanceof TypeError ? '无法连接上传服务，请检查后端是否启动。' : err.message || '上传失败，请检查后端连接')
    } finally {
      setUploading(false)
      pendingUpload.current = false
    }
  }

  return (
    <div>
      <input type="file" accept=".pdf" onChange={handleFileChange} disabled={uploading} />
      <p>支持含文字的 PDF：最多 20 MiB、200 页、提取文字 100000 字符。</p>
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
