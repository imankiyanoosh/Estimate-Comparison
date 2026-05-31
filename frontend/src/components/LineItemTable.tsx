import { useState } from 'react'
import type { LineMatch } from '../types'

type FilterType = 'all' | 'missing_from_carrier' | 'qty_diff' | 'price_diff' | 'only_in_carrier' | 'unresolved' | 'exact_match'

const STATE_BADGE: Record<string, { label: string; cls: string }> = {
  exact_match: { label: 'Match', cls: 'bg-green-100 text-green-800' },
  qty_diff: { label: 'Qty Diff', cls: 'bg-yellow-100 text-yellow-800' },
  price_diff: { label: 'Price Diff', cls: 'bg-orange-100 text-orange-800' },
  scope_diff: { label: 'Scope Diff', cls: 'bg-orange-100 text-orange-800' },
  missing_from_carrier: { label: 'Missing', cls: 'bg-red-100 text-red-800' },
  only_in_carrier: { label: 'Carrier Only', cls: 'bg-gray-100 text-gray-700' },
  unresolved: { label: 'Unresolved', cls: 'bg-gray-100 text-gray-600' },
}

function fmt(v: number | null | undefined) {
  if (v == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v)
}

const FILTERS: { key: FilterType; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'missing_from_carrier', label: 'Missing' },
  { key: 'qty_diff', label: 'Qty Diff' },
  { key: 'price_diff', label: 'Price Diff' },
  { key: 'only_in_carrier', label: 'Carrier Only' },
  { key: 'unresolved', label: 'Unresolved' },
  { key: 'exact_match', label: 'Matched' },
]

export default function LineItemTable({
  matches,
  jobId,
  reviewMode = false,
}: {
  matches: LineMatch[]
  jobId: string
  reviewMode?: boolean
}) {
  const [filter, setFilter] = useState<FilterType>('all')
  const [search, setSearch] = useState('')

  const filtered = matches.filter(m => {
    if (filter !== 'all' && m.match_state !== filter) return false
    if (search) {
      const q = search.toLowerCase()
      const paDesc = m.pa_item?.description_raw?.toLowerCase() || ''
      const cDesc = m.carrier_item?.description_raw?.toLowerCase() || ''
      if (!paDesc.includes(q) && !cDesc.includes(q)) return false
    }
    return true
  })

  return (
    <div>
      {!reviewMode && (
        <h3 className="text-lg font-bold text-gray-800 mb-4">Line-Item Comparison</h3>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors ${
              filter === f.key
                ? 'bg-blue-700 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {f.label}
            <span className="ml-1 opacity-70">
              {f.key === 'all'
                ? matches.length
                : matches.filter(m => m.match_state === f.key).length}
            </span>
          </button>
        ))}

        <input
          type="text"
          placeholder="Search descriptions..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="ml-auto px-3 py-1.5 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-200"
        />
      </div>

      <div className="text-xs text-gray-400 mb-2">{filtered.length} items shown</div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-800 text-white">
              <th className="text-left px-3 py-2 rounded-tl-lg w-24">Status</th>
              <th className="text-left px-3 py-2">PA Description</th>
              <th className="text-right px-3 py-2">PA Qty</th>
              <th className="text-right px-3 py-2">PA Unit $</th>
              <th className="text-right px-3 py-2">PA RCV</th>
              <th className="text-left px-3 py-2">Carrier Description</th>
              <th className="text-right px-3 py-2">Carrier Qty</th>
              <th className="text-right px-3 py-2">Carrier Unit $</th>
              <th className="text-right px-3 py-2">Carrier RCV</th>
              <th className="text-right px-3 py-2 rounded-tr-lg">RCV Delta</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={10} className="text-center py-8 text-gray-400">
                  No items match the current filter
                </td>
              </tr>
            ) : (
              filtered.map((m, i) => {
                const badge = STATE_BADGE[m.match_state] || { label: m.match_state, cls: 'bg-gray-100 text-gray-600' }
                const pa = m.pa_item
                const ca = m.carrier_item
                const rcvDelta = m.rcv_delta
                const rowBg = i % 2 === 0 ? 'bg-white' : 'bg-gray-50'
                const isMissing = m.match_state === 'missing_from_carrier'
                const rowHighlight = isMissing ? 'bg-red-50 hover:bg-red-100' : `${rowBg} hover:bg-gray-100`

                return (
                  <tr key={m.id} className={`border-b ${rowHighlight} transition-colors`}>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${badge.cls}`}>
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-3 py-2 max-w-xs">
                      <div className="text-gray-800">{pa?.description_raw || '—'}</div>
                      {pa?.room_name && (
                        <div className="text-gray-400 text-xs mt-0.5">{pa.room_name}</div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-700">{pa?.qty ?? '—'}</td>
                    <td className="px-3 py-2 text-right text-gray-700">{fmt(pa?.unit_price)}</td>
                    <td className="px-3 py-2 text-right font-medium text-blue-700">{fmt(pa?.rcv)}</td>
                    <td className="px-3 py-2 max-w-xs">
                      <div className="text-gray-700">{ca?.description_raw || '—'}</div>
                      {ca?.room_name && (
                        <div className="text-gray-400 text-xs mt-0.5">{ca.room_name}</div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-700">{ca?.qty ?? '—'}</td>
                    <td className="px-3 py-2 text-right text-gray-700">{fmt(ca?.unit_price)}</td>
                    <td className="px-3 py-2 text-right text-gray-700">{fmt(ca?.rcv)}</td>
                    <td className={`px-3 py-2 text-right font-bold ${
                      rcvDelta > 0.01 ? 'text-red-600' : rcvDelta < -0.01 ? 'text-green-700' : 'text-gray-400'
                    }`}>
                      {rcvDelta > 0.01 ? '+' : ''}{fmt(rcvDelta)}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
