import type { CategoryBreakdown } from '../types'

function fmt(v: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v)
}

export default function CategoryBreakdown({ categories }: { categories: CategoryBreakdown[] }) {
  if (!categories.length) return <p className="text-gray-400">No category data available.</p>

  return (
    <div>
      <h3 className="text-lg font-bold text-gray-800 mb-4">Category Summary</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-blue-700 text-white">
              <th className="text-left px-4 py-3 rounded-tl-lg">Code</th>
              <th className="text-left px-4 py-3">Category</th>
              <th className="text-right px-4 py-3">PA RCV</th>
              <th className="text-right px-4 py-3">Carrier RCV</th>
              <th className="text-right px-4 py-3">Delta</th>
              <th className="text-right px-4 py-3">Variance %</th>
              <th className="text-right px-4 py-3 rounded-tr-lg">Missing</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((c, i) => {
              const delta = c.rcv_delta
              return (
                <tr key={i} className={`border-b ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                  <td className="px-4 py-3 font-mono font-medium text-blue-700">{c.category_code}</td>
                  <td className="px-4 py-3">{c.category_name}</td>
                  <td className="px-4 py-3 text-right">{fmt(c.pa_rcv)}</td>
                  <td className="px-4 py-3 text-right">{fmt(c.carrier_rcv)}</td>
                  <td className={`px-4 py-3 text-right font-semibold ${delta > 0 ? 'text-red-600' : delta < 0 ? 'text-green-600' : 'text-gray-500'}`}>
                    {delta > 0 ? '+' : ''}{fmt(delta)}
                  </td>
                  <td className={`px-4 py-3 text-right ${Math.abs(c.pct_variance) > 20 ? 'text-red-600 font-semibold' : 'text-gray-600'}`}>
                    {c.pct_variance > 0 ? '+' : ''}{c.pct_variance.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-right">
                    {c.missing_count > 0 ? (
                      <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
                        {c.missing_count}
                      </span>
                    ) : '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
