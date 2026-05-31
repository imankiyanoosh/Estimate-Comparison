import { Routes, Route } from 'react-router-dom'
import UploadPage from './components/UploadPage'
import JobStatusPage from './components/JobStatusPage'
import ReportPage from './components/ReportPage'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-blue-800 text-white px-6 py-4 shadow">
        <div className="max-w-7xl mx-auto flex items-center gap-3">
          <span className="text-2xl">📋</span>
          <div>
            <h1 className="text-xl font-bold">Estimate Reconciliation</h1>
            <p className="text-blue-200 text-sm">Xactimate Carrier vs PA Comparison</p>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/jobs/:jobId" element={<JobStatusPage />} />
          <Route path="/jobs/:jobId/report" element={<ReportPage />} />
        </Routes>
      </main>
    </div>
  )
}
