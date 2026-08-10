import { useState } from 'react'

function Upload() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState('')

  function handleFileChange(e) {
    setSelectedFile(e.target.files[0])
  }

  async function handleUpload() {
    const formData = new FormData()
    formData.append('file', selectedFile)

    setUploading(true)
    try {
      const res = await fetch('http://127.0.0.1:8000/upload', {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      setPreview(data.preview)
    } catch (err) {
      console.error(err)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div>
      <input type="file" accept=".pdf" onChange={handleFileChange} />
      {selectedFile && <p>已选择：{selectedFile.name}</p>}

      <button onClick={handleUpload} disabled={!selectedFile || uploading}>
        {uploading ? '上传中...' : '上传'}
      </button>

      {preview && <p>{preview}</p>}
    </div>
  )
}

export default Upload