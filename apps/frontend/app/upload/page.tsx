'use client'
import { useState } from 'react'
import axios from 'axios'

export default function Upload() {
  const [files, setFiles] = useState<FileList | null>(null)
  const [msg, setMsg] = useState('')
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'

  const doUpload = async () => {
    if (!files || files.length === 0) return
    const form = new FormData()
    Array.from(files).forEach(f => form.append('files', f))
    const res = await axios.post(`${API_BASE}/rfp/ingest`, form, { headers: {'Content-Type':'multipart/form-data'} })
    setMsg(JSON.stringify(res.data))
  }

  return (
    <div>
      <h2>Upload RFP</h2>
      <input type="file" multiple onChange={e=>setFiles(e.target.files)} />
      <button onClick={doUpload} style={{marginLeft:10}}>Upload</button>
      <pre>{msg}</pre>
    </div>
  )
}
