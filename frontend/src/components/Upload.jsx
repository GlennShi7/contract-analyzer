import { useRef, useState } from 'react'
import Icon from './Icon'
import { useLanguage } from '../language'
import ErrorMessage from './ErrorMessage'

const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const maxFileBytes = 20 * 1024 * 1024

function Upload({ onUploaded, document }) {
  const { t } = useLanguage()
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
    <section className={`upload-panel panel${document ? ' compact' : ''}`} aria-labelledby="upload-title">
      <div className="section-heading"><span className="section-number">01</span><h2 id="upload-title">{t("导入合同")}</h2></div>
      <p className="section-description">{t("先让文字清楚地呈现，再看重要约定。")}</p>
      <label className={`upload-dropzone${uploading ? ' disabled' : ''}`} htmlFor="contract-file">
        <input id="contract-file" className="file-input" type="file" accept=".pdf" onChange={handleFileChange}
          disabled={uploading} aria-label={t("选择 PDF 合同")} aria-describedby="upload-limits" />
        <span className="upload-symbol"><Icon name={selectedFile ? 'document' : 'upload'} size={24} /></span>
        <strong>{selectedFile ? selectedFile.name : t("选择一份 PDF 合同")}</strong>
        <small>{selectedFile ? t("点击更换文件") : t("点击此处选择文件 · 需要含可读取文字")}</small>
      </label>
      <p className="upload-limits" id="upload-limits">{t("支持含文字的 PDF：最多 20 MiB、200 页、提取文字 100000 字符。")}</p>
      <div className="upload-actions">
        <button className="primary-button" onClick={handleUpload} disabled={!selectedFile || uploading}>
          {uploading ? t("上传中...") : t("上传")}<Icon name="arrow" size={16} />
        </button>
        <span>{document ? t("可更换文件，开始下一份合同") : t("选择文件后，点击上传")}</span>
      </div>
      {error && <ErrorMessage message={error} fallback="上传失败，请重试" />}
      {preview && <details className="upload-preview"><summary>{t("查看提取的文字预览")}</summary><p>{preview}</p></details>}
    </section>
  )
}

export default Upload
