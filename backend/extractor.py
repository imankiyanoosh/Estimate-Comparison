"""
Xactimate PDF Extractor — Enhanced Pipeline
  PDF → PyMuPDF → Page Split → PaddleOCR (scanned pages) →
  Layout Detection → LLM Extraction → JSON
"""
import re
import json
import base64
import logging
import os
import io
from typing import Optional

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
VISION_MODEL = os.environ.get("VISION_MODEL", "google/gemini-2.0-flash-exp:free")

# ---------------------------------------------------------------------------
# PaddleOCR — optional, graceful fallback
# ---------------------------------------------------------------------------
PADDLE_AVAILABLE = False
_paddle_ocr = None

def _init_paddle():
    global PADDLE_AVAILABLE, _paddle_ocr
    if _paddle_ocr is not None:
        return
    try:
        from paddleocr import PaddleOCR
        _paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        PADDLE_AVAILABLE = True
        logger.info("PaddleOCR initialised successfully")
    except Exception as e:
        logger.warning(f"PaddleOCR not available ({e}) — scanned pages will use vision-only mode")
        PADDLE_AVAILABLE = False


CATEGORY_NAMES = {
    "ACT": "Acoustical Treatment", "APL": "Appliances", "AWN": "Awnings",
    "CAB": "Cabinetry", "CLN": "Cleaning", "CNT": "Contents",
    "CON": "Concrete", "DOR": "Doors", "DRY": "Drywall",
    "ELE": "Electrical", "EQS": "Equipment - Specialty",
    "FCW": "Floor Covering - Wood", "FCC": "Floor Covering - Carpet",
    "FCP": "Floor Covering - Pad", "FCH": "Floor Covering - Hard",
    "FEN": "Fencing", "FIN": "Finish Carpentry/Millwork",
    "FRM": "Framing & Rough Carpentry", "FUL": "Fuel Systems",
    "GLS": "Glass", "GUT": "Gutters/Downspouts",
    "HVC": "HVAC", "INS": "Insulation", "LAB": "General Labor",
    "LSC": "Landscaping", "MAS": "Masonry", "MSC": "Miscellaneous",
    "PBD": "Paneling/Ceilings", "PCV": "Plumbing",
    "PNT": "Painting", "PWR": "Power Washing",
    "RFG": "Roofing", "SAF": "Safety Equipment",
    "SFG": "Scaffolding", "SHG": "Siding",
    "STL": "Steel", "STP": "Structural - Post Frame",
    "TIL": "Tile", "TMP": "Temporary Repairs",
    "WIN": "Windows", "WLD": "Welding",
}


# ---------------------------------------------------------------------------
# Step 1 — PyMuPDF helpers
# ---------------------------------------------------------------------------

def render_page_to_png(page, dpi: int = 200) -> bytes:
    """Render a PyMuPDF page to PNG bytes."""
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("png")


def get_pymupdf_text(page) -> str:
    return page.get_text("text")


# ---------------------------------------------------------------------------
# Step 2 — Scanned-page detection
# ---------------------------------------------------------------------------

def is_scanned_page(page, page_text: str) -> bool:
    """
    True if the page is a raster scan rather than native-text PDF.
    Heuristic: sparse selectable text + at least one embedded raster image.
    """
    if len(page_text.strip()) > 150:
        return False
    images = page.get_images(full=False)
    return len(images) >= 1


# ---------------------------------------------------------------------------
# Step 3 — PaddleOCR (scanned pages)
# ---------------------------------------------------------------------------

def run_paddleocr(image_bytes: bytes) -> str:
    """Run PaddleOCR on PNG bytes; return concatenated text lines."""
    _init_paddle()
    if not PADDLE_AVAILABLE or _paddle_ocr is None:
        return ""
    try:
        import numpy as np
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)
        result = _paddle_ocr.ocr(img_array, cls=True)
        lines = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    txt, conf = line[1]
                    if conf > 0.4:
                        lines.append(txt)
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"PaddleOCR error: {e}")
        return ""


# ---------------------------------------------------------------------------
# Step 4 — Layout detection via PyMuPDF block/span structure
# ---------------------------------------------------------------------------

def detect_layout(page) -> dict:
    """
    Analyse PyMuPDF text dict to find room headers and confirm table presence.
    Returns hints consumed by the LLM prompt.
    """
    try:
        blocks = page.get_text("dict", flags=11)["blocks"]
    except Exception:
        return {"room_headers": [], "has_table": False}

    room_headers = []
    has_table = False
    prev_y = 0.0

    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                flags = span.get("flags", 0)
                size = span.get("size", 10)
                y0 = span.get("origin", (0, 0))[1]
                gap = y0 - prev_y
                prev_y = y0

                is_bold = bool(flags & 2**4)
                is_large = size >= 11

                if (is_bold or is_large) and gap > 6:
                    if re.match(r"^[A-Z][A-Za-z\s/\-']{2,40}$", text):
                        room_headers.append(text)

                if re.search(r"\$[\d,]+|\d{3,}\.\d{2}", text):
                    has_table = True

    return {
        "room_headers": list(dict.fromkeys(room_headers))[:20],
        "has_table": has_table,
    }


# ---------------------------------------------------------------------------
# Step 5 — Page-type classification
# ---------------------------------------------------------------------------

def detect_page_type(page_text: str) -> str:
    lower = page_text.lower()
    if any(x in lower for x in ["insured:", "claim number", "price list:", "date of loss", "date entered"]):
        return "cover"
    if "recap by room" in lower or "room recap" in lower:
        return "recap_room"
    if "recap by category" in lower or "category recap" in lower:
        return "recap_category"
    if ("replacement cost" in lower and "actual cash" in lower) and len(page_text) < 1500:
        return "summary"
    dollar_count = len(re.findall(r"\$[\d,]+\.?\d*|\b\d{1,3}(?:,\d{3})*\.\d{2}\b", page_text))
    if dollar_count >= 4:
        return "line_items"
    return "other"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def normalize_description(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_json_from_response(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group())
    raise ValueError("No JSON object found in response")


def coerce_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(",", "").replace("$", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Step 6 — LLM extraction (image + OCR text + layout hints)
# ---------------------------------------------------------------------------

def extract_page_with_llm(
    image_bytes: bytes,
    page_num: int,
    page_type: str,
    ocr_text: str = "",
    layout: Optional[dict] = None,
) -> dict:
    """Send page image (+ pre-extracted text) to OpenRouter vision LLM."""
    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
    except Exception as e:
        logger.error(f"OpenRouter client init failed: {e}")
        return {"line_items": [], "page_type": page_type}

    img_b64 = base64.standard_b64encode(image_bytes).decode()

    ocr_block = ""
    if ocr_text.strip():
        ocr_block = (
            "\n\nPRE-EXTRACTED OCR TEXT — use to verify numbers; "
            "prefer these values over your own reading when disagreement exists:\n"
            f"```\n{ocr_text[:3000]}\n```"
        )

    layout_block = ""
    if layout and layout.get("room_headers"):
        headers = ", ".join(layout["room_headers"])
        layout_block = f"\n\nDETECTED ROOM HEADERS ON THIS PAGE: {headers}"

    if page_type == "cover":
        prompt = f"""This is the cover/header page of an Xactimate insurance estimate PDF.
Extract all available fields. Return ONLY this JSON (null for missing, 0.0 for missing numbers):
{{
  "page_type": "cover",
  "insured_name": null,
  "claim_number": null,
  "policy_number": null,
  "date_of_loss": null,
  "date_entered": null,
  "price_list_code": null,
  "estimator_name": null,
  "company": null,
  "property_address": null,
  "total_rcv": 0.0,
  "total_acv": 0.0,
  "overhead_pct": 0.0,
  "profit_pct": 0.0,
  "line_items": []
}}{ocr_block}"""

    elif page_type == "recap_room":
        prompt = f"""This is a 'Recap by Room' page from an Xactimate estimate PDF.
Extract all room totals. Return ONLY this JSON:
{{
  "page_type": "recap_room",
  "totals": [
    {{"name": "Room Name", "rcv": 0.0, "depreciation": 0.0, "acv": 0.0}}
  ],
  "line_items": []
}}{ocr_block}"""

    elif page_type == "recap_category":
        prompt = f"""This is a 'Recap by Category' page from an Xactimate estimate PDF.
Extract all category totals. Return ONLY this JSON:
{{
  "page_type": "recap_category",
  "totals": [
    {{"code": "DRY", "name": "Drywall", "rcv": 0.0, "depreciation": 0.0, "acv": 0.0}}
  ],
  "line_items": []
}}{ocr_block}"""

    else:
        prompt = f"""This is a line-item page from an Xactimate insurance estimate PDF.

Column order: Description | Qty | Unit | Unit Price | Tax | RCV | Dep% | Dep$ | ACV
- Room section headers: bold/larger text (e.g. "KITCHEN", "Master Bedroom")
- Category codes: 2-4 uppercase letters at start of description (DRY, PNT, RFG, ELE, PCV, FCW, CAB, HVC, INS, WIN, DOR, FRM, MSC …)
- Activity codes: R&R, Remove, Replace, Detach & Reset, Install, Clean
- Do NOT include room subtotal rows or page total rows{layout_block}{ocr_block}

Extract EVERY line item with a dollar amount in RCV. Return ONLY this JSON:
{{
  "page_type": "line_items",
  "rooms_on_page": ["Room Name"],
  "line_items": [
    {{
      "room_name": "Kitchen",
      "category_code": "DRY",
      "selector_code": "1/2",
      "activity_code": "R&R",
      "description_raw": "Drywall - hung, taped, heavy texture, ready for paint",
      "qty": 245.00,
      "unit": "SF",
      "unit_price": 2.15,
      "tax": 0.00,
      "rcv": 526.75,
      "depreciation": 0.00,
      "acv": 526.75
    }}
  ]
}}

Rules:
- Use 0.0 for blank/dash fields
- room_name: most recent room header above the item; "General" if none visible
- If OCR text and image disagree on a dollar amount, prefer the OCR value"""

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        raw = response.choices[0].message.content
        result = parse_json_from_response(raw)
        n = len(result.get("line_items", []))
        logger.info(f"  Page {page_num + 1}: {page_type} → {n} items extracted")
        return result

    except json.JSONDecodeError as e:
        raw_snippet = raw[:300] if "raw" in dir() else "N/A"
        logger.error(f"  Page {page_num + 1}: JSON parse error — {e} | raw={raw_snippet}")
        return {"line_items": [], "page_type": page_type, "_error": f"JSON parse: {e}"}
    except Exception as e:
        logger.error(f"  Page {page_num + 1}: OpenRouter error — {type(e).__name__}: {e}")
        return {"line_items": [], "page_type": page_type, "_error": str(e)}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def extract_estimate(pdf_path: str, source: str) -> dict:
    """
    Full pipeline:
      PDF → PyMuPDF → scan detection → PaddleOCR (if scanned) →
      layout detection → LLM extraction → structured JSON
    """
    import fitz  # PyMuPDF

    metadata = {
        "insured_name": None,
        "claim_number": None,
        "date_entered": None,
        "price_list_code": None,
        "estimator_name": None,
        "total_rcv": 0.0,
        "total_acv": 0.0,
        "overhead_pct": 10.0,
        "profit_pct": 10.0,
    }
    all_line_items = []
    qa_issues = []
    recap_room_totals = {}

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return {
            "metadata": metadata,
            "line_items": [],
            "qa_results": {
                "passed": False,
                "issues": [f"Cannot open PDF: {e}"],
                "extraction_confidence": 0.0,
                "total_items": 0,
            },
        }

    total_pages = len(doc)
    logger.info(f"[{source}] Starting enhanced extraction of {total_pages} pages…")

    current_room = "General"

    for page_num in range(total_pages):
        page = doc[page_num]

        # ── 1. PyMuPDF text ──────────────────────────────────────────────
        page_text = get_pymupdf_text(page)

        # ── 2. Scan detection ────────────────────────────────────────────
        scanned = is_scanned_page(page, page_text)

        if not scanned and len(page_text.strip()) < 30:
            logger.info(f"  Page {page_num + 1}/{total_pages}: empty — skip")
            continue

        # ── 3. PaddleOCR (scanned pages only) ────────────────────────────
        ocr_text = ""
        if scanned:
            logger.info(f"  Page {page_num + 1}/{total_pages}: scanned — running PaddleOCR")
            image_bytes_ocr = render_page_to_png(page, dpi=200)
            ocr_text = run_paddleocr(image_bytes_ocr)
            effective_text = ocr_text if ocr_text else page_text
        else:
            effective_text = page_text

        # ── 4. Layout detection ──────────────────────────────────────────
        layout = detect_layout(page)
        page_type = detect_page_type(effective_text)

        logger.info(
            f"  Page {page_num + 1}/{total_pages}: type='{page_type}' "
            f"scanned={scanned} ocr_chars={len(ocr_text)} "
            f"room_headers={layout.get('room_headers', [])[:3]}"
        )

        # ── 5. Render for LLM ────────────────────────────────────────────
        image_bytes = render_page_to_png(page, dpi=200)

        # ── 6. LLM extraction ────────────────────────────────────────────
        result = extract_page_with_llm(
            image_bytes, page_num, page_type,
            ocr_text=ocr_text,
            layout=layout,
        )

        # Cover page
        if page_type == "cover":
            for field in [
                "insured_name", "claim_number", "date_entered", "price_list_code",
                "estimator_name", "overhead_pct", "profit_pct",
            ]:
                val = result.get(field)
                if val not in (None, "", 0, 0.0):
                    metadata[field] = val
            for field in ["total_rcv", "total_acv"]:
                val = coerce_float(result.get(field))
                if val > 0:
                    metadata[field] = val

        # Recap room
        if page_type == "recap_room":
            for t in result.get("totals", []):
                name = t.get("name", "")
                rcv = coerce_float(t.get("rcv"))
                if name and rcv:
                    recap_room_totals[name.lower().strip()] = rcv

        # Track current room
        rooms_on_page = result.get("rooms_on_page", [])
        if rooms_on_page:
            current_room = rooms_on_page[-1]

        # Line items
        for item in result.get("line_items", []):
            if not item.get("room_name"):
                item["room_name"] = current_room

            for field in ["qty", "unit_price", "tax", "rcv", "depreciation", "acv"]:
                item[field] = coerce_float(item.get(field))

            item["description_normalized"] = normalize_description(
                item.get("description_raw", "")
            )
            item["source_page"] = page_num
            item["unit"] = str(item.get("unit") or "").strip()

            desc_lower = item.get("description_raw", "").lower()
            item["is_misc"] = item.get("category_code") == "MSC" or "misc" in desc_lower
            item["is_code_upgrade"] = bool(
                re.search(r"code\s+upgrade|ordinance|code\s+req", desc_lower)
            )

            qty = item["qty"]
            up = item["unit_price"]
            rcv = item["rcv"]
            if qty > 0 and up > 0 and rcv > 0:
                expected = qty * up
                conf = 1.0 if abs(expected - rcv) / max(rcv, 0.01) <= 0.12 else 0.75
            else:
                conf = 0.85
            item["extraction_confidence"] = conf

            all_line_items.append(item)

    doc.close()

    if metadata["total_rcv"] == 0.0 and all_line_items:
        metadata["total_rcv"] = sum(i["rcv"] for i in all_line_items)

    if not all_line_items:
        qa_issues.append("No line items could be extracted from this PDF.")
        if not OPENROUTER_API_KEY:
            qa_issues.append("OPENROUTER_API_KEY is not set — extraction is disabled.")

    valid = sum(1 for i in all_line_items if i["extraction_confidence"] >= 0.85)
    extraction_confidence = valid / max(len(all_line_items), 1)

    logger.info(
        f"[{source}] Done: {len(all_line_items)} items, "
        f"confidence={extraction_confidence:.2f}, "
        f"paddle={'on' if PADDLE_AVAILABLE else 'off'}"
    )

    return {
        "metadata": metadata,
        "line_items": all_line_items,
        "qa_results": {
            "passed": len(qa_issues) == 0,
            "issues": qa_issues,
            "extraction_confidence": extraction_confidence,
            "total_items": len(all_line_items),
            "recap_room_totals": recap_room_totals,
        },
    }
