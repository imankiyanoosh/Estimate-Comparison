import { useState, useRef, DragEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { createJob } from '../api'

function DropZone({
  label,
  sublabel,
  file,
  onFile,
  color,
}: {
  label: string
  sublabel: string
  file: File | null
  onFile: (f: File) => void
  color: string
}) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function handleDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f && f.name.toLowerCase().endsWith('.pdf')) onFile(f)
  }

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
        dragging ? 'border-blue-500 bg-blue-50' : file ? `border-${color}-400 bg-${color}-50` : 'border-gray-300 hover:border-gray-400'
      }`}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f) }}
      />
      <div className="text-4xl mb-3">{file ? '✅' : '📄'}</div>
      <div className="font-semibold text-gray-700">{label}</div>
      <div className="text-sm text-gray-500 mt-1">{sublabel}</div>
      {file ? (
        <div className="mt-3 text-sm font-medium text-green-700 bg-green-100 rounded px-3 py-1 inline-block">
          {file.name} ({(file.size / 1024 / 1024).toFixed(1)} MB)
        </div>
      ) : (
        <div className="mt-3 text-xs text-gray-400">Drop PDF here or click to browse</div>
      )}
    </div>
  )
}

export default function UploadPage() {
  const [carrierFile, setCarrierFile] = useState<File | null>(null)
  const [paFile, setPaFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  async function handleSubmit() {
    if (!carrierFile || !paFile) return
    setLoading(true)
    setError(null)
    try {
      const { job_id } = await createJob(carrierFile, paFile)
      navigate(`/jobs/${job_id}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Upload failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">Compare Two Estimates</h2>
        <p className="text-gray-500 mb-8">
          Upload the carrier (insurance) estimate and your PA rebuild estimate. The system will extract
          all line items, match them, and produce a detailed reconciliation report.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <DropZone
            label="Insurance / Carrier Estimate"
            sublabel="The estimate approved by the carrier"
            file={carrierFile}
            onFile={setCarrierFile}
            color="blue"
          />
          <DropZone
            label="PA / Rebuild Estimate"
            sublabel="Your public adjuster estimate"
            file={paFile}
            onFile={setPaFile}
            color="green"
          />
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
            {error}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={!carrierFile || !paFile || loading}
          className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-xl transition-colors text-lg"
        >
          {loading ? 'Uploading...' : 'Compare Estimates'}
        </button>

        <div className="mt-6 p-4 bg-blue-50 rounded-xl text-sm text-blue-800">
          <strong>What happens next:</strong> The system will extract every line item from both PDFs,
          match them using category codes and descriptions, and show you exactly where scope, quantities,
          and prices differ.
        </div>
      </div>
    </div>
  )
}
