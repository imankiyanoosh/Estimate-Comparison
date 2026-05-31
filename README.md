# Xactimate Estimate Reconciliation MVP

A full-stack web app that compares two Xactimate-generated PDF estimates (carrier vs PA) and produces an interactive reconciliation report plus a downloadable PDF.

## Architecture

- **Backend**: FastAPI + SQLAlchemy (SQLite) + PyMuPDF + pdfplumber + rapidfuzz + scikit-learn
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs at http://localhost:5173 and proxies `/api` requests to the backend at port 8000.

## How It Works

1. Upload two Xactimate PDFs (carrier/insurance estimate + PA/rebuild estimate)
2. Backend extracts all line items using PyMuPDF with column-detection, falling back to pdfplumber
3. Three-tier matching engine (exact code → fuzzy description → TF-IDF semantic) with Hungarian algorithm assignment
4. Interactive report with tabs: Summary, By Room, By Category, Line Items, Financial Deltas, Review Queue
5. Export as PDF (ReportLab) or CSV

## API Endpoints

- `POST /api/jobs` — Upload two PDFs, start processing
- `GET /api/jobs/{id}` — Get job status
- `GET /api/jobs/{id}/report` — Get full reconciliation report JSON
- `GET /api/jobs/{id}/export/pdf` — Download PDF report
- `GET /api/jobs/{id}/export/csv` — Download CSV of line matches
- `POST /api/jobs/{id}/matches/{match_id}/review` — Mark match as human-reviewed
