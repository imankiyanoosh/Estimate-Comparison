import uuid
from collections import defaultdict
from extractor import CATEGORY_NAMES


def compute_room_aggregates(matches: list, job_id: str) -> list[dict]:
    """Compute per-room aggregates from match results."""
    rooms = defaultdict(lambda: {
        "carrier_rcv": 0.0,
        "pa_rcv": 0.0,
        "line_count_carrier": 0,
        "line_count_pa": 0,
        "missing_count": 0,
    })

    for match in matches:
        pa_item = match.get("pa_item")
        carrier_item = match.get("carrier_item")

        # Determine room from whichever item exists
        if pa_item:
            room = pa_item.get("room_name") or "General"
        elif carrier_item:
            room = carrier_item.get("room_name") or "General"
        else:
            room = "General"

        if carrier_item:
            rooms[room]["carrier_rcv"] += carrier_item.get("rcv", 0.0)
            rooms[room]["line_count_carrier"] += 1
        if pa_item:
            rooms[room]["pa_rcv"] += pa_item.get("rcv", 0.0)
            rooms[room]["line_count_pa"] += 1
        if match.get("match_state") == "missing_from_carrier":
            rooms[room]["missing_count"] += 1

    result = []
    for room_name, data in rooms.items():
        result.append({
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "room_name": room_name,
            "carrier_rcv": data["carrier_rcv"],
            "pa_rcv": data["pa_rcv"],
            "rcv_delta": data["pa_rcv"] - data["carrier_rcv"],
            "line_count_carrier": data["line_count_carrier"],
            "line_count_pa": data["line_count_pa"],
            "missing_count": data["missing_count"],
        })

    result.sort(key=lambda x: abs(x["rcv_delta"]), reverse=True)
    return result


def compute_category_aggregates(matches: list, job_id: str) -> list[dict]:
    """Compute per-category aggregates from match results."""
    cats = defaultdict(lambda: {
        "carrier_rcv": 0.0,
        "pa_rcv": 0.0,
        "missing_count": 0,
    })

    for match in matches:
        pa_item = match.get("pa_item")
        carrier_item = match.get("carrier_item")

        # Determine category
        if pa_item and pa_item.get("category_code"):
            cat = pa_item["category_code"]
        elif carrier_item and carrier_item.get("category_code"):
            cat = carrier_item["category_code"]
        else:
            cat = "MSC"

        if carrier_item:
            cats[cat]["carrier_rcv"] += carrier_item.get("rcv", 0.0)
        if pa_item:
            cats[cat]["pa_rcv"] += pa_item.get("rcv", 0.0)
        if match.get("match_state") == "missing_from_carrier":
            cats[cat]["missing_count"] += 1

    result = []
    for cat_code, data in cats.items():
        carrier_rcv = data["carrier_rcv"]
        pa_rcv = data["pa_rcv"]
        rcv_delta = pa_rcv - carrier_rcv
        pct_variance = 0.0
        if carrier_rcv > 0:
            pct_variance = (rcv_delta / carrier_rcv) * 100
        elif pa_rcv > 0:
            pct_variance = 100.0

        result.append({
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "category_code": cat_code,
            "category_name": CATEGORY_NAMES.get(cat_code, cat_code),
            "carrier_rcv": carrier_rcv,
            "pa_rcv": pa_rcv,
            "rcv_delta": rcv_delta,
            "pct_variance": pct_variance,
            "missing_count": data["missing_count"],
        })

    result.sort(key=lambda x: abs(x["rcv_delta"]), reverse=True)
    return result


def compute_financial_deltas(
    carrier_estimate: dict, pa_estimate: dict, matches: list, job_id: str
) -> list[dict]:
    """Compute financial deltas for overhead, profit, tax, depreciation, etc."""
    deltas = []

    def make_delta(kind, carrier_val, pa_val, rationale=""):
        return {
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "kind": kind,
            "carrier_value": carrier_val,
            "pa_value": pa_val,
            "delta": pa_val - carrier_val,
            "rationale": rationale,
        }

    # Overhead %
    c_oh = carrier_estimate.get("overhead_pct", 0.0)
    p_oh = pa_estimate.get("overhead_pct", 0.0)
    deltas.append(make_delta(
        "overhead", c_oh, p_oh,
        "Overhead percentage applied to labor and material costs"
    ))

    # Profit %
    c_profit = carrier_estimate.get("profit_pct", 0.0)
    p_profit = pa_estimate.get("profit_pct", 0.0)
    deltas.append(make_delta(
        "profit", c_profit, p_profit,
        "Profit percentage applied to labor and material costs"
    ))

    # Total tax (sum from line items)
    carrier_tax = sum(
        m["carrier_item"].get("tax", 0.0)
        for m in matches
        if m.get("carrier_item")
    )
    pa_tax = sum(
        m["pa_item"].get("tax", 0.0)
        for m in matches
        if m.get("pa_item")
    )
    deltas.append(make_delta(
        "material_tax", carrier_tax, pa_tax,
        "Total material tax across all line items"
    ))

    # Total depreciation
    carrier_dep = sum(
        m["carrier_item"].get("depreciation", 0.0)
        for m in matches
        if m.get("carrier_item")
    )
    pa_dep = sum(
        m["pa_item"].get("depreciation", 0.0)
        for m in matches
        if m.get("pa_item")
    )
    deltas.append(make_delta(
        "depreciation", carrier_dep, pa_dep,
        "Total depreciation applied across all line items"
    ))

    # Total RCV
    c_rcv = carrier_estimate.get("total_rcv", 0.0)
    p_rcv = pa_estimate.get("total_rcv", 0.0)
    deltas.append(make_delta(
        "total_rcv", c_rcv, p_rcv,
        "Total Replacement Cost Value as reported on estimate cover page"
    ))

    # Total ACV
    c_acv = carrier_estimate.get("total_acv", 0.0)
    p_acv = pa_estimate.get("total_acv", 0.0)
    deltas.append(make_delta(
        "total_acv", c_acv, p_acv,
        "Total Actual Cash Value as reported on estimate cover page"
    ))

    return deltas
