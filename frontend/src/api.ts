import axios from 'axios'
import type { JobStatus, ReportData } from './types'

// In production on Railway, set VITE_API_URL to your backend URL
// e.g. https://your-backend.railway.app
const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '') + '/api'

const api = axios.create({ baseURL: BASE_URL })

export async function createJob(carrierPdf: File, paPdf: File): Promise<{ job_id: string }> {
  const form = new FormData()
  form.append('carrier_pdf', carrierPdf)
  form.append('pa_pdf', paPdf)
  const res = await api.post('/jobs', form)
  return res.data
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await api.get(`/jobs/${jobId}`)
  return res.data
}

export async function getReport(jobId: string): Promise<ReportData> {
  const res = await api.get(`/jobs/${jobId}/report`)
  return res.data
}

export function exportPdfUrl(jobId: string): string {
  return `${BASE_URL}/jobs/${jobId}/export/pdf`
}

export function exportCsvUrl(jobId: string): string {
  return `${BASE_URL}/jobs/${jobId}/export/csv`
}

export async function reviewMatch(jobId: string, matchId: string, action: string, newState?: string) {
  await api.post(`/jobs/${jobId}/matches/${matchId}/review`, { action, new_state: newState })
}
