# Xactimate Estimate Reconciliation App

A web app that compares two Xactimate-generated PDF estimates — insurance/carrier vs public-adjuster rebuild — and produces a detailed reconciliation report showing scope, quantity, and price discrepancies at line, room, category, and total levels.

## Architecture

- **Backend**: FastAPI (Python) + SQLite + PyMuPDF + pdfplumber + rapidfuzz
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

Open http://localhost:5173

## Features

- Upload carrier and PA estimate PDFs
- Extracts line items using PyMuPDF (text-based PDFs) with pdfplumber fallback
- 3-tier matching engine: exact code → fuzzy description → semantic TF-IDF
- QA checks: validates qty × unit_price ≈ RCV for each extracted line
- Interactive report with tabs: Summary, By Room, By Category, Line Items, Financial Deltas, Review Queue
- Export to PDF (ReportLab) and CSV
- Human review queue for low-confidence matches
- Price list mismatch warning

## Match States

| State | Meaning |
|-------|---------|
| `exact_match` | Same item, same values |
| `qty_diff` | Same item, quantity reduced by carrier |
| `price_diff` | Same item, price reduced by carrier |
| `scope_diff` | Matched but total differs |
| `missing_from_carrier` | In PA estimate but NOT in carrier — supplement opportunity |
| `only_in_carrier` | In carrier but not in PA estimate |
| `unresolved` | Low-confidence match — needs human review |

## Roadmap

- Phase 2: Building code upgrade / ordinance-or-law suggestion engine
- Phase 2: Estimate quality review ("what did we miss?")
- Phase 2: Supplement narrative generation via Claude
- Phase 3: OCR support for scanned PDFs (AWS Textract / Azure Document Intelligence)
- Phase 3: ESX file ingestion
- Phase 3: Carrier-specific comparison profiles
