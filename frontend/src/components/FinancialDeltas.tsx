import type { FinancialDelta } from '../types'

function fmt(v: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v)
}

const KIND_LABELS: Record<string, string> = {
  overhead: 'Overhead %',
  profit: 'Profit %',
  material_tax: 'Material Tax',
  labor_tax: 'Labor Tax',
  depreciation: 'Depreciation',
  total_rcv: 'Total RCV',
  total_acv: 'Total ACV',
  deductible: 'Deductible',
}

export default function FinancialDeltas({ deltas }: { deltas: FinancialDelta[] }) {
  if (!deltas.length) return <p className="text-gray-400">No financial data available.</p>

  return (
    <div>
      <h3 className="text-lg font-bold text-gray-800 mb-2">Financial Deltas</h3>
      <p className="text-sm text-gray-500 mb-4">
        These differences are in add-ons and estimate-level financials, separate from line-item scope discrepancies.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-blue-700 text-white">
              <th className="text-left px-4 py-3 rounded-tl-lg">Component</th>
              <th className="text-right px-4 py-3">PA Value</th>
              <th className="text-right px-4 py-3">Carrier Value</th>
              <th className="text-right px-4 py-3">Delta</th>
              <th className="text-left px-4 py-3 rounded-tr-lg">Notes</th>
            </tr>
          </thead>
          <tbody>
            {deltas.map((d, i) => {
              const delta = d.delta
              return (
                <tr key={i} className={`border-b ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                  <td className="px-4 py-3 font-medium">{KIND_LABELS[d.kind] || d.kind}</td>
                  <td className="px-4 py-3 text-right">{fmt(d.pa_value)}</td>
                  <td className="px-4 py-3 text-right">{fmt(d.carrier_value)}</td>
                  <td className={`px-4 py-3 text-right font-semibold ${delta > 0 ? 'text-red-600' : delta < 0 ? 'text-green-600' : 'text-gray-500'}`}>
                    {delta > 0 ? '+' : ''}{fmt(delta)}
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{d.rationale || '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
