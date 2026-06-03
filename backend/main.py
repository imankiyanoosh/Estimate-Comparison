import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from database import (
    create_tables, ComparisonJob, Estimate, LineItem,
    LineMatch, RoomAggregate, CategoryAggregate, FinancialDelta, SessionLocal
)
from extractor import extract_estimate
from matcher import match_estimates
from aggregator import compute_room_aggregates, compute_category_aggregates, compute_financial_deltas
from report_generator import generate_pdf_report, generate_csv_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Xactimate Estimate Reconciliation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("/tmp/estimate_jobs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

create_tables()


def job_to_dict(job: ComparisonJob) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "carrier_filename": job.carrier_filename,
        "pa_filename": job.pa_filename,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "error_message": job.error_message,
    }


def estimate_to_dict(est: Estimate) -> dict:
    return {
        "id": est.id,
        "job_id": est.job_id,
        "source": est.source,
        "price_list_code": est.price_list_code,
        "estimator_name": est.estimator_name,
        "insured_name": est.insured_name,
        "claim_number": est.claim_number,
        "date_entered": est.date_entered,
        "total_rcv": est.total_rcv,
        "total_acv": est.total_acv,
        "overhead_pct": est.overhead_pct,
        "profit_pct": est.profit_pct,
        "extraction_confidence": est.extraction_confidence,
        "qa_passed": est.qa_passed,
        "qa_issues": json.loads(est.qa_issues or "[]"),
    }


def line_item_to_dict(item: LineItem) -> dict:
    return {
        "id": item.id,
        "estimate_id": item.estimate_id,
        "room_name": item.room_name,
        "category_code": item.category_code,
        "selector_code": item.selector_code,
        "activity_code": item.activity_code,
        "description_raw": item.description_raw,
        "description_normalized": item.description_normalized,
        "qty": item.qty,
        "unit": item.unit,
        "unit_price": item.unit_price,
        "tax": item.tax,
        "rcv": item.rcv,
        "depreciation": item.depreciation,
        "acv": item.acv,
        "source_page": item.source_page,
        "is_misc": item.is_misc,
        "is_code_upgrade": item.is_code_upgrade,
        "extraction_confidence": item.extraction_confidence,
    }


def line_match_to_dict(match: LineMatch, db) -> dict:
    carrier_item = None
    pa_item = None
    if match.carrier_line_id:
        li = db.query(LineItem).filter(LineItem.id == match.carrier_line_id).first()
        if li:
            carrier_item = line_item_to_dict(li)
    if match.pa_line_id:
        li = db.query(LineItem).filter(LineItem.id == match.pa_line_id).first()
        if li:
            pa_item = line_item_to_dict(li)
    return {
        "id": match.id,
        "job_id": match.job_id,
        "carrier_line_id": match.carrier_line_id,
        "pa_line_id": match.pa_line_id,
        "carrier_item": carrier_item,
        "pa_item": pa_item,
        "match_type": match.match_type,
        "match_state": match.match_state,
        "confidence": match.confidence,
        "qty_delta": match.qty_delta,
        "unit_price_delta": match.unit_price_delta,
        "rcv_delta": match.rcv_delta,
        "score_breakdown": json.loads(match.score_breakdown or "{}"),
        "human_reviewed": match.human_reviewed,
    }


def process_job(job_id: str, carrier_path: str, pa_path: str):
    """Background processing: extract, match, aggregate."""
    db = SessionLocal()
    try:
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
        if not job:
            return

        # Step 1: Extract carrier
        job.status = "extracting"
        db.commit()

        logger.info(f"[{job_id}] Extracting carrier estimate...")
        carrier_result = extract_estimate(carrier_path, "carrier")
        carrier_meta = carrier_result["metadata"]
        carrier_items_raw = carrier_result["line_items"]
        carrier_qa = carrier_result["qa_results"]

        carrier_est = Estimate(
            id=str(uuid.uuid4()),
            job_id=job_id,
            source="carrier",
            price_list_code=carrier_meta.get("price_list_code"),
            estimator_name=carrier_meta.get("estimator_name"),
            insured_name=carrier_meta.get("insured_name"),
            claim_number=carrier_meta.get("claim_number"),
            date_entered=carrier_meta.get("date_entered"),
            total_rcv=carrier_meta.get("total_rcv", 0.0),
            total_acv=carrier_meta.get("total_acv", 0.0),
            overhead_pct=carrier_meta.get("overhead_pct", 0.0),
            profit_pct=carrier_meta.get("profit_pct", 0.0),
            extraction_confidence=carrier_qa.get("extraction_confidence", 0.0),
            qa_passed=carrier_qa.get("passed", False),
            qa_issues=json.dumps(carrier_qa.get("issues", [])),
        )
        db.add(carrier_est)
        db.flush()

        carrier_line_items = []
        for item_data in carrier_items_raw:
            clean = {k: v for k, v in item_data.items() if k != "_idx"}
            li = LineItem(id=str(uuid.uuid4()), estimate_id=carrier_est.id, **clean)
            db.add(li)
            item_data["_db_id"] = li.id
            carrier_line_items.append(item_data)
        db.commit()

        # Step 2: Extract PA
        logger.info(f"[{job_id}] Extracting PA estimate...")
        pa_result = extract_estimate(pa_path, "pa")
        pa_meta = pa_result["metadata"]
        pa_items_raw = pa_result["line_items"]
        pa_qa = pa_result["qa_results"]

        pa_est = Estimate(
            id=str(uuid.uuid4()),
            job_id=job_id,
            source="pa",
            price_list_code=pa_meta.get("price_list_code"),
            estimator_name=pa_meta.get("estimator_name"),
            insured_name=pa_meta.get("insured_name"),
            claim_number=pa_meta.get("claim_number"),
            date_entered=pa_meta.get("date_entered"),
            total_rcv=pa_meta.get("total_rcv", 0.0),
            total_acv=pa_meta.get("total_acv", 0.0),
            overhead_pct=pa_meta.get("overhead_pct", 0.0),
            profit_pct=pa_meta.get("profit_pct", 0.0),
            extraction_confidence=pa_qa.get("extraction_confidence", 0.0),
            qa_passed=pa_qa.get("passed", False),
            qa_issues=json.dumps(pa_qa.get("issues", [])),
        )
        db.add(pa_est)
        db.flush()

        pa_line_items = []
        for item_data in pa_items_raw:
            clean = {k: v for k, v in item_data.items() if k != "_idx"}
            li = LineItem(id=str(uuid.uuid4()), estimate_id=pa_est.id, **clean)
            db.add(li)
            item_data["_db_id"] = li.id
            pa_line_items.append(item_data)
        db.commit()

        # Step 3: Match
        job.status = "matching"
        db.commit()

        logger.info(f"[{job_id}] Matching {len(carrier_line_items)} carrier vs {len(pa_line_items)} PA items...")
        raw_matches = match_estimates(carrier_line_items, pa_line_items)

        for m in raw_matches:
            carrier_item = m.get("carrier_item")
            pa_item = m.get("pa_item")
            lm = LineMatch(
                id=str(uuid.uuid4()),
                job_id=job_id,
                carrier_line_id=carrier_item.get("_db_id") if carrier_item else None,
                pa_line_id=pa_item.get("_db_id") if pa_item else None,
                match_type=m.get("match_type"),
                match_state=m.get("match_state"),
                confidence=m.get("confidence", 0.0),
                qty_delta=m.get("qty_delta", 0.0),
                unit_price_delta=m.get("unit_price_delta", 0.0),
                rcv_delta=m.get("rcv_delta", 0.0),
                score_breakdown=m.get("score_breakdown", "{}"),
                human_reviewed=False,
            )
            db.add(lm)
        db.commit()

        # Step 4: Aggregates
        logger.info(f"[{job_id}] Computing aggregates...")
        room_aggs = compute_room_aggregates(raw_matches, job_id)
        for ra in room_aggs:
            db.add(RoomAggregate(**ra))

        cat_aggs = compute_category_aggregates(raw_matches, job_id)
        for ca in cat_aggs:
            db.add(CategoryAggregate(**ca))

        carrier_meta_full = {
            **carrier_meta,
            "overhead_pct": carrier_est.overhead_pct,
            "profit_pct": carrier_est.profit_pct,
            "total_rcv": carrier_est.total_rcv,
            "total_acv": carrier_est.total_acv,
        }
        pa_meta_full = {
            **pa_meta,
            "overhead_pct": pa_est.overhead_pct,
            "profit_pct": pa_est.profit_pct,
            "total_rcv": pa_est.total_rcv,
            "total_acv": pa_est.total_acv,
        }
        fin_deltas = compute_financial_deltas(carrier_meta_full, pa_meta_full, raw_matches, job_id)
        for fd in fin_deltas:
            db.add(FinancialDelta(**fd))

        db.commit()

        job.status = "complete"
        db.commit()
        logger.info(f"[{job_id}] Processing complete!")

    except Exception as e:
        logger.exception(f"[{job_id}] Processing failed: {e}")
        db.rollback()
        try:
            job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@app.post("/api/jobs")
async def create_job(
    carrier_pdf: UploadFile = File(...),
    pa_pdf: UploadFile = File(...),
):
    """Upload two PDF estimates and start reconciliation processing."""
    for f in [carrier_pdf, pa_pdf]:
        if not (f.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"File {f.filename} must be a PDF")

    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    carrier_path = str(job_dir / "carrier.pdf")
    pa_path = str(job_dir / "pa.pdf")

    content = await carrier_pdf.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Carrier PDF exceeds 50MB limit")
    with open(carrier_path, "wb") as fh:
        fh.write(content)

    content = await pa_pdf.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PA PDF exceeds 50MB limit")
    with open(pa_path, "wb") as fh:
        fh.write(content)

    db = SessionLocal()
    try:
        job = ComparisonJob(
            id=job_id,
            status="queued",
            carrier_pdf_path=carrier_path,
            pa_pdf_path=pa_path,
            carrier_filename=carrier_pdf.filename,
            pa_filename=pa_pdf.filename,
            created_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
    finally:
        db.close()

    thread = Thread(target=process_job, args=(job_id, carrier_path, pa_path), daemon=True)
    thread.start()

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Get job status and basic info."""
    db = SessionLocal()
    try:
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        result = job_to_dict(job)

        if job.status == "complete":
            matches = db.query(LineMatch).filter(LineMatch.job_id == job_id).all()
            result["total_matches"] = len(matches)
            result["missing_count"] = sum(1 for m in matches if m.match_state == "missing_from_carrier")

        return result
    finally:
        db.close()


@app.get("/api/jobs/{job_id}/report")
def get_report(job_id: str):
    """Get full reconciliation report."""
    db = SessionLocal()
    try:
        job = db.query(ComparisonJob).filter(ComparisonJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status not in ("complete", "failed"):
            raise HTTPException(status_code=202, detail=f"Job is still processing: {job.status}")

        estimates = db.query(Estimate).filter(Estimate.job_id == job_id).all()
        carrier_est = next((e for e in estimates if e.source == "carrier"), None)
        pa_est = next((e for e in estimates if e.source == "pa"), None)

        matches = db.query(LineMatch).filter(LineMatch.job_id == job_id).all()
        matches_dicts = [line_match_to_dict(m, db) for m in matches]

        room_aggs = db.query(RoomAggregate).filter(RoomAggregate.job_id == job_id).all()
        cat_aggs = db.query(CategoryAggregate).filter(CategoryAggregate.job_id == job_id).all()
        fin_deltas = db.query(FinancialDelta).filter(FinancialDelta.job_id == job_id).all()

        pa_total = pa_est.total_rcv if pa_est else 0
        carrier_total = carrier_est.total_rcv if carrier_est else 0

        if pa_total == 0:
            pa_total = sum(
                m["pa_item"]["rcv"] for m in matches_dicts
                if m.get("pa_item") and m["pa_item"].get("rcv")
            )
        if carrier_total == 0:
            carrier_total = sum(
                m["carrier_item"]["rcv"] for m in matches_dicts
                if m.get("carrier_item") and m["carrier_item"].get("rcv")
            )

        matched_count = sum(1 for m in matches_dicts if m["match_state"] == "exact_match")
        missing_count = sum(1 for m in matches_dicts if m["match_state"] == "missing_from_carrier")
        only_in_carrier = sum(1 for m in matches_dicts if m["match_state"] == "only_in_carrier")
        qty_diff_count = sum(1 for m in matches_dicts if m["match_state"] == "qty_diff")
        price_diff_count = sum(1 for m in matches_dicts if m["match_state"] == "price_diff")
        unresolved_count = sum(1 for m in matches_dicts if m["match_state"] == "unresolved")

        c_pl = carrier_est.price_list_code if carrier_est else None
        p_pl = pa_est.price_list_code if pa_est else None
        price_list_warning = bool(c_pl and p_pl and c_pl != p_pl)

        exec_summary = {
            "pa_total": pa_total,
            "carrier_total": carrier_total,
            "total_delta": pa_total - carrier_total,
            "matched_count": matched_count,
            "exact_match_count": matched_count,
            "missing_count": missing_count,
            "only_in_carrier_count": only_in_carrier,
            "qty_diff_count": qty_diff_count,
            "price_diff_count": price_diff_count,
            "unresolved_count": unresolved_count,
            "price_list_warning": price_list_warning,
        }

        unmatched_pa = [
            m["pa_item"] for m in matches_dicts
            if m["match_state"] == "missing_from_carrier" and m.get("pa_item")
        ]
        unmatched_carrier = [
            m["carrier_item"] for m in matches_dicts
            if m["match_state"] == "only_in_carrier" and m.get("carrier_item")
        ]

        return {
            "job": job_to_dict(job),
            "carrier_estimate": estimate_to_dict(carrier_est) if carrier_est else None,
            "pa_estimate": estimate_to_dict(pa_est) if pa_est else None,
            "executive_summary": exec_summary,
            "room_breakdown": [
                {
                    "id": r.id, "room_name": r.room_name,
                    "carrier_rcv": r.carrier_rcv, "pa_rcv": r.pa_rcv,
                    "rcv_delta": r.rcv_delta,
                    "line_count_carrier": r.line_count_carrier,
                    "line_count_pa": r.line_count_pa,
                    "missing_count": r.missing_count,
                }
                for r in room_aggs
            ],
            "category_breakdown": [
                {
                    "id": c.id, "category_code": c.category_code,
                    "category_name": c.category_name,
                    "carrier_rcv": c.carrier_rcv, "pa_rcv": c.pa_rcv,
                    "rcv_delta": c.rcv_delta, "pct_variance": c.pct_variance,
                    "missing_count": c.missing_count,
                }
                for c in cat_aggs
            ],
            "line_matches": matches_dicts,
            "financial_deltas": [
                {
                    "id": f.id, "kind": f.kind,
                    "carrier_value": f.carrier_value, "pa_value": f.pa_value,
                    "delta": f.delta, "rationale": f.rationale,
                }
                for f in fin_deltas
            ],
            "unmatched_pa": unmatched_pa,
            "unmatched_carrier": unmatched_carrier,
        }
    finally:
        db.close()


@app.get("/api/jobs/{job_id}/export/pdf")
def export_pdf(job_id: str):
    """Download PDF reconciliation report."""
    import tempfile
    report_data = get_report(job_id)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        generate_pdf_report(report_data, tmp_path)
        with open(tmp_path, "rb") as fh:
            pdf_bytes = fh.read()
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=reconciliation_{job_id[:8]}.pdf"},
    )


@app.get("/api/jobs/{job_id}/export/csv")
def export_csv(job_id: str):
    """Download CSV of line matches."""
    report_data = get_report(job_id)
    csv_content = generate_csv_report(report_data["line_matches"])
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=line_matches_{job_id[:8]}.csv"},
    )


@app.post("/api/jobs/{job_id}/matches/{match_id}/review")
def review_match(job_id: str, match_id: str, action: dict):
    """Mark a match as human reviewed and optionally update its state."""
    db = SessionLocal()
    try:
        match = db.query(LineMatch).filter(
            LineMatch.id == match_id, LineMatch.job_id == job_id
        ).first()
        if not match:
            raise HTTPException(status_code=404, detail="Match not found")

        match.human_reviewed = True
        if "match_state" in action:
            match.match_state = action["match_state"]

        db.commit()
        return {"id": match.id, "human_reviewed": True, "match_state": match.match_state}
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/test-vision")
def test_vision():
    """Test OpenRouter connectivity and vision capability."""
    import os, base64
    from openai import OpenAI

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("VISION_MODEL", "google/gemini-2.0-flash-exp:free")

    if not api_key:
        return {"ok": False, "error": "OPENROUTER_API_KEY is not set", "model": model}

    # 1x1 white PNG
    tiny_png = base64.standard_b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI6QAAAABJRU5ErkJggg=="
    )
    img_b64 = base64.standard_b64encode(tiny_png).decode()

    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=20,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                {"type": "text", "text": "Reply with just the word OK."},
            ]}],
        )
        reply = resp.choices[0].message.content
        return {"ok": True, "model": model, "reply": reply}
    except Exception as e:
        return {"ok": False, "model": model, "error": f"{type(e).__name__}: {e}"}
