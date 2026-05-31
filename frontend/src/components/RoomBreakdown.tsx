import type { RoomBreakdown } from '../types'

function fmt(v: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v)
}

export default function RoomBreakdown({ rooms }: { rooms: RoomBreakdown[] }) {
  if (!rooms.length) return <p className="text-gray-400">No room data available.</p>

  return (
    <div>
      <h3 className="text-lg font-bold text-gray-800 mb-4">Room-by-Room Comparison</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-blue-700 text-white">
              <th className="text-left px-4 py-3 rounded-tl-lg">Room</th>
              <th className="text-right px-4 py-3">PA RCV</th>
              <th className="text-right px-4 py-3">Carrier RCV</th>
              <th className="text-right px-4 py-3">Delta</th>
              <th className="text-right px-4 py-3">PA Lines</th>
              <th className="text-right px-4 py-3">Carrier Lines</th>
              <th className="text-right px-4 py-3 rounded-tr-lg">Missing</th>
            </tr>
          </thead>
          <tbody>
            {rooms.map((r, i) => {
              const delta = r.rcv_delta
              return (
                <tr key={i} className={`border-b ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                  <td className="px-4 py-3 font-medium">{r.room_name}</td>
                  <td className="px-4 py-3 text-right">{fmt(r.pa_rcv)}</td>
                  <td className="px-4 py-3 text-right">{fmt(r.carrier_rcv)}</td>
                  <td className={`px-4 py-3 text-right font-semibold ${delta > 0 ? 'text-red-600' : delta < 0 ? 'text-green-600' : 'text-gray-500'}`}>
                    {delta > 0 ? '+' : ''}{fmt(delta)}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">{r.line_count_pa}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{r.line_count_carrier}</td>
                  <td className="px-4 py-3 text-right">
                    {r.missing_count > 0 ? (
                      <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
                        {r.missing_count}
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
