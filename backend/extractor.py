"""
Xactimate PDF Extractor — Claude Vision, page-by-page.
Each page is rendered to an image and sent to Claude for structured extraction.
"""
import re
import json
import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
# Any vision-capable model on OpenRouter works, e.g.:
#   google/gemini-2.0-flash-exp:free
#   anthropic/claude-sonnet-4-5
#   openai/gpt-4o
#   openai/gpt-4o-mini
VISION_MODEL = os.environ.get("VISION_MODEL", "google/gemini-2.0-flash-exp:free")

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


def normalize_description(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def render_page_to_png(page, dpi: int = 150) -> bytes:
    """Render a PyMuPDF page to PNG bytes."""
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("png")


def detect_page_type(page_text: str) -> str:
    """Quick heuristic to classify a page before sending to Claude."""
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


def parse_json_from_response(text: str) -> dict:
    """Extract JSON from Claude's response, handling markdown code blocks."""
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    # Find first { ... } block
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group())
    raise ValueError("No JSON object found in response")


def extract_page_with_claude(image_bytes: bytes, page_num: int, page_type: str) -> dict:
    """Send one page image to OpenRouter and return structured extraction."""
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

    if page_type == "cover":
        prompt = """This is the cover or header page of an Xactimate insurance estimate PDF.

Extract all available information and return ONLY this JSON (use null for missing fields, 0.0 for missing numbers):
{
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
}"""

    elif page_type == "recap_room":
        prompt = """This is a 'Recap by Room' page from an Xactimate estimate PDF.
Extract all room totals and return ONLY this JSON:
{
  "page_type": "recap_room",
  "totals": [
    {"name": "Room Name", "rcv": 0.0, "depreciation": 0.0, "acv": 0.0}
  ],
  "line_items": []
}"""

    elif page_type == "recap_category":
        prompt = """This is a 'Recap by Category' page from an Xactimate estimate PDF.
Extract all category totals and return ONLY this JSON:
{
  "page_type": "recap_category",
  "totals": [
    {"code": "DRY", "name": "Drywall", "rcv": 0.0, "depreciation": 0.0, "acv": 0.0}
  ],
  "line_items": []
}"""

    else:
        prompt = """This is a line-item page from an Xactimate insurance estimate PDF.

Xactimate structure:
- Room section headers appear as bold/larger text with the room name (e.g., "KITCHEN", "Master Bedroom")
- Each line item row has: Description | Qty | Unit | Unit Price | Tax | RCV | Dep% | Dep$ | ACV
- The Description column often starts with a category code (2-4 uppercase letters like DRY, PNT, RFG, ELE, PCV, FCW, CAB, HVC, INS, WIN, DOR, FRM, MSC)
- After the category code comes the selector code, then activity (R&R, Remove, Replace, etc.)

Extract EVERY line item on this page. Return ONLY this JSON:
{
  "page_type": "line_items",
  "rooms_on_page": ["Room Name"],
  "line_items": [
    {
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
    }
  ]
}

Rules:
- Include every line item row that has a dollar amount in RCV column
- Use 0.0 for any blank/dash numeric fields
- room_name: use the most recent room header above the item; use "General" if none visible
- category_code: the 2-4 letter code at start of description (null if not identifiable)
- activity_code: R&R, Remove, Replace, Detach & Reset, Install, Clean, etc. (null if not present)
- Do NOT include room subtotal rows or page total rows as line items"""

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}",
                        },
                    },
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
        logger.warning(f"  Page {page_num + 1}: JSON parse error — {e}")
        return {"line_items": [], "page_type": page_type}
    except Exception as e:
        logger.warning(f"  Page {page_num + 1}: Claude error — {e}")
        return {"line_items": [], "page_type": page_type}


def coerce_float(val) -> float:
    """Safely convert a value to float."""
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(",", "").replace("$", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


def extract_estimate(pdf_path: str, source: str) -> dict:
    """
    Extract all line items from a PDF using Claude Vision, page by page.
    Returns: {metadata, line_items, qa_results}
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
    logger.info(f"[{source}] Starting extraction of {total_pages} pages...")

    current_room = "General"

    for page_num in range(total_pages):
        page = doc[page_num]
        page_text = page.get_text()
        page_type = detect_page_type(page_text)

        # Skip completely empty pages
        if page_type == "other" and len(page_text.strip()) < 30:
            logger.info(f"  Page {page_num + 1}/{total_pages}: empty — skip")
            continue

        logger.info(f"  Page {page_num + 1}/{total_pages}: detected as '{page_type}'")

        # Render and send to Claude
        image_bytes = render_page_to_png(page, dpi=150)
        result = extract_page_with_claude(image_bytes, page_num, page_type)

        # --- Handle cover page ---
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

        # --- Handle recap pages (store for QA) ---
        if page_type == "recap_room":
            for t in result.get("totals", []):
                name = t.get("name", "")
                rcv = coerce_float(t.get("rcv"))
                if name and rcv:
                    recap_room_totals[name.lower().strip()] = rcv

        # --- Track current room across pages ---
        rooms_on_page = result.get("rooms_on_page", [])
        if rooms_on_page:
            current_room = rooms_on_page[-1]

        # --- Process line items ---
        for item in result.get("line_items", []):
            if not item.get("room_name"):
                item["room_name"] = current_room

            # Coerce all numeric fields
            for field in ["qty", "unit_price", "tax", "rcv", "depreciation", "acv"]:
                item[field] = coerce_float(item.get(field))

            # Normalize description
            item["description_normalized"] = normalize_description(
                item.get("description_raw", "")
            )
            item["source_page"] = page_num
            item["unit"] = str(item.get("unit") or "").strip()

            # Flags
            desc_lower = item.get("description_raw", "").lower()
            item["is_misc"] = (
                item.get("category_code") == "MSC" or "misc" in desc_lower
            )
            item["is_code_upgrade"] = bool(
                re.search(r"code\s+upgrade|ordinance|code\s+req", desc_lower)
            )

            # Confidence: arithmetic check where possible
            qty = item["qty"]
            up = item["unit_price"]
            rcv = item["rcv"]
            if qty > 0 and up > 0 and rcv > 0:
                expected = qty * up
                conf = 1.0 if abs(expected - rcv) / max(rcv, 0.01) <= 0.12 else 0.75
            else:
                conf = 0.85  # Claude-extracted but no check
            item["extraction_confidence"] = conf

            all_line_items.append(item)

    doc.close()

    # --- Backfill metadata totals from line items if missing ---
    if metadata["total_rcv"] == 0.0 and all_line_items:
        metadata["total_rcv"] = sum(i["rcv"] for i in all_line_items)

    # --- QA ---
    if not all_line_items:
        qa_issues.append("No line items could be extracted from this PDF.")
        if not OPENROUTER_API_KEY:
            qa_issues.append("OPENROUTER_API_KEY is not set — Vision extraction is disabled.")

    valid = sum(1 for i in all_line_items if i["extraction_confidence"] >= 0.85)
    extraction_confidence = valid / max(len(all_line_items), 1)

    logger.info(
        f"[{source}] Done: {len(all_line_items)} items, confidence={extraction_confidence:.2f}"
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
