import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getReport, exportPdfUrl, exportCsvUrl } from '../api'
import type { ReportData } from '../types'
import ExecutiveSummary from './ExecutiveSummary'
import RoomBreakdown from './RoomBreakdown'
import CategoryBreakdown from './CategoryBreakdown'
import LineItemTable from './LineItemTable'
import FinancialDeltas from './FinancialDeltas'

const TABS = ['Summary', 'By Room', 'By Category', 'Line Items', 'Financial', 'Review Queue']

export default function ReportPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const [report, setReport] = useState<ReportData | null>(null)
  const [tab, setTab] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!jobId) return
    getReport(jobId)
      .then(setReport)
      .catch(e => setError(e.message || 'Failed to load report'))
      .finally(() => setLoading(false))
  }, [jobId])

  if (loading) return <div className="text-center py-16 text-gray-500">Loading report...</div>
  if (error) return <div className="text-center py-16 text-red-600">{error}</div>
  if (!report) return null

  const exec = report.executive_summary
  const unresolvedMatches = report.line_matches.filter(m => m.match_state === 'unresolved')

  return (
    <div>
      {/* Header bar */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 mb-4 flex items-center justify-between">
        <div>
          <h2 className="font-bold text-gray-800">Reconciliation Report</h2>
          <p className="text-sm text-gray-500">
            {report.job.carrier_filename} vs {report.job.pa_filename}
          </p>
        </div>
        <div className="flex gap-2">
          <a
            href={exportCsvUrl(jobId!)}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
          >
            Export CSV
          </a>
          <a
            href={exportPdfUrl(jobId!)}
            className="px-4 py-2 text-sm bg-blue-700 text-white rounded-lg hover:bg-blue-800 font-medium"
          >
            Download PDF Report
          </a>
        </div>
      </div>

      {exec.price_list_warning && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-300 rounded-xl text-amber-800 text-sm font-medium">
          ⚠ Warning: The two estimates use different price lists ({report.carrier_estimate?.price_list_code} vs {report.pa_estimate?.price_list_code}). Some differences may reflect pricing context, not scope disagreements.
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-white rounded-xl border border-gray-100 shadow-sm p-1">
        {TABS.map((t, i) => (
          <button
            key={t}
            onClick={() => setTab(i)}
            className={`flex-1 py-2 px-3 text-sm font-medium rounded-lg transition-colors ${
              tab === i ? 'bg-blue-700 text-white' : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {t}
            {t === 'Review Queue' && unresolvedMatches.length > 0 && (
              <span className="ml-1 bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5">
                {unresolvedMatches.length}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        {tab === 0 && <ExecutiveSummary report={report} />}
        {tab === 1 && <RoomBreakdown rooms={report.room_breakdown} />}
        {tab === 2 && <CategoryBreakdown categories={report.category_breakdown} />}
        {tab === 3 && <LineItemTable matches={report.line_matches} jobId={jobId!} />}
        {tab === 4 && <FinancialDeltas deltas={report.financial_deltas} />}
        {tab === 5 && <LineItemTable matches={unresolvedMatches} jobId={jobId!} reviewMode />}
      </div>
    </div>
  )
}
