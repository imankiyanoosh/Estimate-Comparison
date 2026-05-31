import type { ReportData } from '../types'

function fmt(v: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v)
}

function StatCard({ label, value, sub, color = 'blue' }: { label: string; value: string; sub?: string; color?: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 border-blue-200 text-blue-800',
    red: 'bg-red-50 border-red-200 text-red-800',
    green: 'bg-green-50 border-green-200 text-green-800',
    orange: 'bg-orange-50 border-orange-200 text-orange-800',
    gray: 'bg-gray-50 border-gray-200 text-gray-600',
  }
  return (
    <div className={`border rounded-xl p-4 ${colors[color]}`}>
      <div className="text-sm font-medium opacity-70">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
      {sub && <div className="text-xs mt-1 opacity-60">{sub}</div>}
    </div>
  )
}

export default function ExecutiveSummary({ report }: { report: ReportData }) {
  const exec = report.executive_summary
  const carrier = report.carrier_estimate
  const pa = report.pa_estimate

  const deltaPositive = exec.total_delta > 0

  return (
    <div>
      <h3 className="text-lg font-bold text-gray-800 mb-4">Executive Summary</h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="PA Estimate Total" value={fmt(exec.pa_total)} color="blue" />
        <StatCard label="Carrier Estimate Total" value={fmt(exec.carrier_total)} color="blue" />
        <StatCard
          label="Total Difference"
          value={fmt(Math.abs(exec.total_delta))}
          sub={deltaPositive ? 'PA is higher — supplement opportunity' : 'Carrier is higher'}
          color={deltaPositive ? 'red' : 'green'}
        />
        <StatCard label="Missing From Carrier" value={String(exec.missing_count)} sub="items not paid" color="red" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
        <StatCard label="Exact Matches" value={String(exec.exact_match_count)} color="green" />
        <StatCard label="Qty Differences" value={String(exec.qty_diff_count)} color="orange" />
        <StatCard label="Price Differences" value={String(exec.price_diff_count)} color="orange" />
        <StatCard label="Only in Carrier" value={String(exec.only_in_carrier_count)} color="gray" />
        <StatCard label="Unresolved" value={String(exec.unresolved_count)} sub="needs review" color="gray" />
      </div>

      <h4 className="font-semibold text-gray-700 mb-3">Document Metadata</h4>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {[{ label: 'Carrier / Insurance Estimate', est: carrier }, { label: 'PA / Rebuild Estimate', est: pa }].map(({ label, est }) => (
          <div key={label} className="border border-gray-200 rounded-xl p-4">
            <div className="font-semibold text-gray-700 mb-3 pb-2 border-b">{label}</div>
            {est ? (
              <dl className="space-y-1 text-sm">
                {[
                  ['Insured', est.insured_name],
                  ['Claim #', est.claim_number],
                  ['Date', est.date_entered],
                  ['Price List', est.price_list_code],
                  ['Estimator', est.estimator_name],
                  ['Total RCV', fmt(est.total_rcv)],
                  ['Total ACV', fmt(est.total_acv)],
                  ['O&P', `${est.overhead_pct}% / ${est.profit_pct}%`],
                  ['Extraction Confidence', `${(est.extraction_confidence * 100).toFixed(0)}%`],
                ].map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <dt className="text-gray-500 w-36 flex-shrink-0">{k}:</dt>
                    <dd className="font-medium text-gray-800">{v || '—'}</dd>
                  </div>
                ))}
                {est.qa_issues.length > 0 && (
                  <div className="mt-2 p-2 bg-amber-50 rounded text-amber-700 text-xs">
                    QA Issues: {est.qa_issues.join('; ')}
                  </div>
                )}
              </dl>
            ) : (
              <p className="text-gray-400 text-sm">Not available</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
