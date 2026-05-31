import re
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

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

ACTIVITY_CODES = {"RR", "REM", "REP", "RES", "DR", "DET", "INS", "CLN", "R&R", "LAB"}

ROOM_KEYWORDS = {
    "kitchen", "bath", "bathroom", "bedroom", "living", "dining", "garage",
    "basement", "attic", "closet", "hallway", "hall", "office", "laundry",
    "entry", "foyer", "porch", "deck", "exterior", "interior", "roof",
    "general", "miscellaneous", "family room", "master", "bonus", "utility",
    "sunroom", "mudroom", "pantry", "study", "library", "den",
}


def normalize_description(text: str) -> str:
    """Normalize description for matching."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_money(text: str) -> float:
    """Parse a money string like '$1,234.56' to float."""
    if not text:
        return 0.0
    cleaned = re.sub(r'[^\d.\-]', '', text.replace(',', ''))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def parse_qty(text: str) -> float:
    """Parse quantity string."""
    if not text:
        return 0.0
    cleaned = re.sub(r'[^\d.\-]', '', text.replace(',', ''))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def extract_metadata_from_text(full_text: str) -> dict:
    """Extract header metadata from the full text of the PDF."""
    metadata = {
        "insured_name": None,
        "claim_number": None,
        "date_entered": None,
        "price_list_code": None,
        "estimator_name": None,
        "total_rcv": 0.0,
        "total_acv": 0.0,
        "overhead_pct": 0.0,
        "profit_pct": 0.0,
    }

    patterns = {
        "insured_name": [
            r"Insured\s*[:\-]\s*(.+?)(?:\n|Claim)",
            r"insured\s*[:\-]\s*(.+?)(?:\n|$)",
        ],
        "claim_number": [
            r"Claim\s*(?:Number|#|No\.?)\s*[:\-]\s*([A-Za-z0-9\-]+)",
            r"Claim\s*[:\-]\s*([A-Za-z0-9\-]+)",
        ],
        "date_entered": [
            r"Date\s*Entered\s*[:\-]\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
            r"Date\s*[:\-]\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
            r"Estimate\s*Date\s*[:\-]\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        ],
        "price_list_code": [
            r"Price\s*List\s*[:\-]\s*([A-Z]{2,4}\d*[A-Z]*_[A-Z]{3}\d{2})",
            r"Price\s*List\s*[:\-]\s*([A-Za-z0-9_\-]{5,20})",
            r"\b([A-Z]{2,5}\d{1,2}[A-Z]_[A-Z]{3}\d{2})\b",
        ],
        "estimator_name": [
            r"Estimator\s*[:\-]\s*(.+?)(?:\n|$)",
            r"Prepared\s*by\s*[:\-]\s*(.+?)(?:\n|$)",
        ],
    }

    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            if match:
                metadata[field] = match.group(1).strip()
                break

    # Extract totals
    rcv_patterns = [
        r"Total\s*RCV\s*[:\-]?\s*\$?([\d,]+\.?\d*)",
        r"Replacement\s*Cost\s*Value\s*[:\-]?\s*\$?([\d,]+\.?\d*)",
        r"Grand\s*Total\s*[:\-]?\s*\$?([\d,]+\.?\d*)",
    ]
    for pattern in rcv_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            metadata["total_rcv"] = parse_money(match.group(1))
            break

    acv_patterns = [
        r"Total\s*ACV\s*[:\-]?\s*\$?([\d,]+\.?\d*)",
        r"Actual\s*Cash\s*Value\s*[:\-]?\s*\$?([\d,]+\.?\d*)",
    ]
    for pattern in acv_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            metadata["total_acv"] = parse_money(match.group(1))
            break

    # O&P
    op_match = re.search(r"Overhead\s*[:\-]?\s*([\d.]+)\s*%", full_text, re.IGNORECASE)
    if op_match:
        metadata["overhead_pct"] = float(op_match.group(1))

    profit_match = re.search(r"Profit\s*[:\-]?\s*([\d.]+)\s*%", full_text, re.IGNORECASE)
    if profit_match:
        metadata["profit_pct"] = float(profit_match.group(1))

    return metadata


def is_room_header(text: str) -> bool:
    """Determine if a text line is likely a room header."""
    stripped = text.strip()
    if not stripped or len(stripped) < 2:
        return False

    # All caps check
    if stripped.isupper() and 3 <= len(stripped) <= 60 and not re.search(r'\d{3}', stripped):
        # Make sure it's not a category code line
        if not re.match(r'^[A-Z]{2,4}\s', stripped):
            return True

    # Check for known room keywords
    lower = stripped.lower()
    for kw in ROOM_KEYWORDS:
        if lower == kw or lower.startswith(kw + " ") or lower.endswith(" " + kw):
            return True

    return False


def extract_category_and_codes(description: str):
    """Extract category code, selector code, and activity code from a description."""
    category_code = None
    selector_code = None
    activity_code = None

    # Try to match known category codes at start
    cat_match = re.match(r'^([A-Z]{2,4})\s+', description)
    if cat_match and cat_match.group(1) in CATEGORY_NAMES:
        category_code = cat_match.group(1)
        rest = description[cat_match.end():]

        # Try selector code
        sel_match = re.match(r'([A-Z0-9]{2,10})\s+', rest)
        if sel_match:
            selector_code = sel_match.group(1)
            rest = rest[sel_match.end():]

        # Try activity code
        act_match = re.match(r'(R&R|RR|REM|REP|RES|DR|DET|INS|CLN|LAB)\b', rest, re.IGNORECASE)
        if act_match:
            activity_code = act_match.group(1).upper()

    if not category_code:
        # Look for any category-like code
        for code in CATEGORY_NAMES:
            if re.search(r'\b' + code + r'\b', description):
                category_code = code
                break

    # Look for activity code anywhere
    if not activity_code:
        act_match = re.search(r'\b(R&R|REM|REP|RES|DR|DET)\b', description, re.IGNORECASE)
        if act_match:
            activity_code = act_match.group(1).upper()

    return category_code, selector_code, activity_code


def spans_to_line_groups(page_dict: dict, y_tolerance: float = 3.0) -> list:
    """Group spans by approximate y-coordinate (same line)."""
    spans_flat = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:  # text block
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if text:
                    bbox = span["bbox"]
                    spans_flat.append({
                        "text": text,
                        "x0": bbox[0],
                        "y0": bbox[1],
                        "x1": bbox[2],
                        "y1": bbox[3],
                        "flags": span.get("flags", 0),
                        "size": span.get("size", 10),
                    })

    if not spans_flat:
        return []

    # Group by y-coordinate
    spans_flat.sort(key=lambda s: (round(s["y0"] / y_tolerance), s["x0"]))
    groups = []
    current_y = None
    current_group = []

    for span in spans_flat:
        y_bucket = round(span["y0"] / y_tolerance)
        if current_y is None:
            current_y = y_bucket
        if abs(y_bucket - current_y) <= 1:
            current_group.append(span)
        else:
            if current_group:
                groups.append(current_group)
            current_group = [span]
            current_y = y_bucket

    if current_group:
        groups.append(current_group)

    return groups


# Column x-boundaries for Xactimate line-item pages (approximate, in points)
COLUMN_BOUNDS = {
    "description": (0, 350),
    "qty": (350, 400),
    "unit": (400, 440),
    "unit_price": (440, 510),
    "tax": (510, 550),
    "rcv": (550, 610),
    "dep": (610, 660),
    "acv": (660, 750),
}


def assign_column(x: float) -> Optional[str]:
    """Assign a span to a column based on its x-coordinate."""
    for col_name, (x_min, x_max) in COLUMN_BOUNDS.items():
        if x_min <= x <= x_max:
            return col_name
    # Handle wider pages - scale proportionally
    if x > 750:
        return "acv"
    return None


def parse_line_item_from_group(group: list, current_room: str, page_num: int) -> Optional[dict]:
    """Parse a span group into a line item dict."""
    col_texts = {}
    for span in group:
        col = assign_column(span["x0"])
        if col:
            if col in col_texts:
                col_texts[col] += " " + span["text"]
            else:
                col_texts[col] = span["text"]

    description = col_texts.get("description", "").strip()
    if not description or len(description) < 3:
        return None

    # Must have at least one numeric column to be a line item
    has_numeric = any(
        col in col_texts for col in ["qty", "unit_price", "rcv", "acv"]
    )
    if not has_numeric:
        return None

    qty = parse_qty(col_texts.get("qty", "0"))
    unit_price = parse_money(col_texts.get("unit_price", "0"))
    tax = parse_money(col_texts.get("tax", "0"))
    rcv = parse_money(col_texts.get("rcv", "0"))
    dep = parse_money(col_texts.get("dep", "0"))
    acv = parse_money(col_texts.get("acv", "0"))
    unit = col_texts.get("unit", "")

    # Skip if all numeric values are zero (likely a header)
    if rcv == 0 and qty == 0 and unit_price == 0:
        return None

    category_code, selector_code, activity_code = extract_category_and_codes(description)

    is_misc = category_code == "MSC" or "misc" in description.lower()
    is_code_upgrade = bool(re.search(r'code\s+upgrade|code\s+req', description, re.IGNORECASE))

    # Calculate confidence: qty * unit_price should approximately equal rcv
    conf = 1.0
    if qty > 0 and unit_price > 0 and rcv > 0:
        expected = qty * unit_price
        if abs(expected - rcv) / max(rcv, 0.01) > 0.05:
            conf = 0.7

    return {
        "room_name": current_room or "General",
        "category_code": category_code,
        "selector_code": selector_code,
        "activity_code": activity_code,
        "description_raw": description,
        "description_normalized": normalize_description(description),
        "qty": qty,
        "unit": unit.strip(),
        "unit_price": unit_price,
        "tax": tax,
        "rcv": rcv,
        "depreciation": dep,
        "acv": acv,
        "source_page": page_num,
        "is_misc": is_misc,
        "is_code_upgrade": is_code_upgrade,
        "extraction_confidence": conf,
    }


def extract_with_pdfplumber(pdf_path: str, page_num: int, current_room: str) -> list:
    """Fallback extraction using pdfplumber for a specific page."""
    items = []
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return items
            page = pdf.pages[page_num]
            table = page.extract_table()
            if not table:
                return items

            for row in table:
                if not row or not row[0]:
                    continue
                description = str(row[0]).strip()
                if not description or len(description) < 3:
                    continue

                def safe_col(idx):
                    if idx < len(row) and row[idx]:
                        return str(row[idx])
                    return "0"

                qty = parse_qty(safe_col(1))
                unit = safe_col(2) if len(row) > 2 else ""
                unit_price = parse_money(safe_col(3))
                tax = parse_money(safe_col(4))
                rcv = parse_money(safe_col(5))
                dep = parse_money(safe_col(6))
                acv = parse_money(safe_col(7))

                if rcv == 0 and qty == 0:
                    continue

                category_code, selector_code, activity_code = extract_category_and_codes(description)
                conf = 1.0
                if qty > 0 and unit_price > 0 and rcv > 0:
                    expected = qty * unit_price
                    if abs(expected - rcv) / max(rcv, 0.01) > 0.05:
                        conf = 0.7

                items.append({
                    "room_name": current_room or "General",
                    "category_code": category_code,
                    "selector_code": selector_code,
                    "activity_code": activity_code,
                    "description_raw": description,
                    "description_normalized": normalize_description(description),
                    "qty": qty,
                    "unit": unit.strip(),
                    "unit_price": unit_price,
                    "tax": tax,
                    "rcv": rcv,
                    "depreciation": dep,
                    "acv": acv,
                    "source_page": page_num,
                    "is_misc": category_code == "MSC",
                    "is_code_upgrade": bool(re.search(r'code\s+upgrade', description, re.IGNORECASE)),
                    "extraction_confidence": conf,
                })
    except Exception as e:
        logger.warning(f"pdfplumber fallback failed on page {page_num}: {e}")

    return items


def extract_estimate(pdf_path: str, source: str) -> dict:
    """
    Extract estimate data from a PDF file.
    Returns dict with metadata, line_items, and qa_results.
    """
    import fitz  # PyMuPDF

    line_items = []
    full_text_parts = []
    current_room = "General"
    qa_issues = []

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return {
            "metadata": {},
            "line_items": [],
            "qa_results": {"passed": False, "issues": [f"Failed to open PDF: {e}"]},
        }

    # Check if text-based
    total_chars = 0
    for page in doc:
        total_chars += len(page.get_text())

    if total_chars < 100:
        qa_issues.append("PDF appears to be image-based; extraction quality may be poor")

    # Extract full text from first 3 pages for metadata
    header_text = ""
    for i in range(min(3, len(doc))):
        header_text += doc[i].get_text()
    full_text_parts.append(header_text)

    metadata = extract_metadata_from_text(header_text)

    # Extract all pages for line items
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_dict = page.get_text("dict")
        full_text_parts.append(page.get_text())

        groups = spans_to_line_groups(page_dict)
        page_items = []

        for group in groups:
            # Check if this group is a room header
            group_text = " ".join(s["text"] for s in group).strip()

            if is_room_header(group_text):
                # Check that it's not just a category line
                if len(group) <= 3 and not any(
                    assign_column(s["x0"]) in ["qty", "rcv", "acv"] for s in group
                ):
                    current_room = group_text.title()
                    continue

            item = parse_line_item_from_group(group, current_room, page_num)
            if item:
                page_items.append(item)

        # Fallback to pdfplumber if few items found
        if len(page_items) < 5 and page_num > 0:
            fallback_items = extract_with_pdfplumber(pdf_path, page_num, current_room)
            if len(fallback_items) > len(page_items):
                page_items = fallback_items

        line_items.extend(page_items)

    doc.close()

    # If metadata totals are missing, try full text
    if metadata["total_rcv"] == 0:
        full_text = "\n".join(full_text_parts)
        meta2 = extract_metadata_from_text(full_text)
        if meta2["total_rcv"] > 0:
            metadata["total_rcv"] = meta2["total_rcv"]
        if meta2["total_acv"] > 0:
            metadata["total_acv"] = meta2["total_acv"]

    # QA check: validate qty * unit_price ~ rcv
    valid_count = 0
    total_count = 0
    for item in line_items:
        if item["qty"] > 0 and item["unit_price"] > 0 and item["rcv"] > 0:
            total_count += 1
            expected = item["qty"] * item["unit_price"]
            if abs(expected - item["rcv"]) / max(item["rcv"], 0.01) <= 0.05:
                valid_count += 1
            else:
                item["extraction_confidence"] = 0.7

    extraction_confidence = valid_count / max(total_count, 1)
    if extraction_confidence < 0.5:
        qa_issues.append(
            f"Only {valid_count}/{total_count} line items pass qty*price≈rcv check"
        )

    if not line_items:
        qa_issues.append("No line items extracted from PDF")

    qa_passed = len(qa_issues) == 0

    return {
        "metadata": metadata,
        "line_items": line_items,
        "qa_results": {
            "passed": qa_passed,
            "issues": qa_issues,
            "extraction_confidence": extraction_confidence,
            "total_items": len(line_items),
        },
    }
