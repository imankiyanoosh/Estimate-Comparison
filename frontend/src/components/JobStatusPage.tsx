import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getJobStatus } from '../api'
import type { JobStatus } from '../types'

const STAGES = [
  { key: 'queued', label: 'Queued' },
  { key: 'extracting', label: 'Extracting Line Items' },
  { key: 'matching', label: 'Matching Items' },
  { key: 'complete', label: 'Complete' },
]

function stageIndex(status: string) {
  const i = STAGES.findIndex(s => s.key === status)
  return i === -1 ? 0 : i
}

export default function JobStatusPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [job, setJob] = useState<JobStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!jobId) return
    const poll = async () => {
      try {
        const j = await getJobStatus(jobId)
        setJob(j)
        if (j.status === 'complete') {
          navigate(`/jobs/${jobId}/report`)
        } else if (j.status === 'failed') {
          setError(j.error_message || 'Processing failed')
        }
      } catch {
        setError('Could not reach server')
      }
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [jobId, navigate])

  const current = job ? stageIndex(job.status) : 0

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">Processing Estimates</h2>
        {job && (
          <div className="text-sm text-gray-500 mb-6">
            <span className="font-medium">{job.carrier_filename}</span> vs{' '}
            <span className="font-medium">{job.pa_filename}</span>
          </div>
        )}

        {error ? (
          <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
            <strong>Error:</strong> {error}
          </div>
        ) : (
          <div className="space-y-4">
            {STAGES.map((stage, i) => (
              <div key={stage.key} className="flex items-center gap-4">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 ${
                  i < current ? 'bg-green-500 text-white' :
                  i === current ? 'bg-blue-600 text-white animate-pulse' :
                  'bg-gray-200 text-gray-400'
                }`}>
                  {i < current ? '✓' : i + 1}
                </div>
                <div className={`font-medium ${i <= current ? 'text-gray-800' : 'text-gray-400'}`}>
                  {stage.label}
                  {i === current && job?.status !== 'complete' && (
                    <span className="ml-2 text-blue-600 text-sm">In progress...</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {!error && job?.status !== 'complete' && job?.status !== 'failed' && (
          <div className="mt-6 text-sm text-gray-500 text-center">
            This typically takes 30–120 seconds depending on PDF size
          </div>
        )}
      </div>
    </div>
  )
}
