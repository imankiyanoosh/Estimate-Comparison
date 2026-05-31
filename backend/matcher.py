import json
import logging
from typing import Optional

import numpy as np
from rapidfuzz import fuzz
from scipy.optimize import linear_sum_assignment
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


def code_similarity(a: dict, b: dict) -> float:
    """Score code similarity between two line items."""
    score = 0.0
    if a.get("category_code") and b.get("category_code"):
        if a["category_code"] == b["category_code"]:
            score += 0.5
    if a.get("selector_code") and b.get("selector_code"):
        if a["selector_code"] == b["selector_code"]:
            score += 0.3
    if a.get("activity_code") and b.get("activity_code"):
        if a["activity_code"] == b["activity_code"]:
            score += 0.2
    return score


def room_similarity(a: dict, b: dict) -> float:
    """Compare room names."""
    ra = (a.get("room_name") or "general").lower().strip()
    rb = (b.get("room_name") or "general").lower().strip()
    if ra == rb:
        return 1.0
    if ra in rb or rb in ra:
        return 0.5
    return 0.0


def qty_proximity(a: dict, b: dict) -> float:
    """Score how close quantities are."""
    qa = a.get("qty", 0)
    qb = b.get("qty", 0)
    if qa == 0 and qb == 0:
        return 1.0
    if qa == 0 or qb == 0:
        return 0.0
    ratio = min(qa, qb) / max(qa, qb)
    return ratio


def unit_match(a: dict, b: dict) -> float:
    """Score unit match."""
    ua = (a.get("unit") or "").lower().strip()
    ub = (b.get("unit") or "").lower().strip()
    if not ua and not ub:
        return 1.0
    if ua == ub:
        return 1.0
    return 0.0


def compute_tfidf_matrix(descriptions: list[str]) -> Optional[object]:
    """Build a TF-IDF matrix from descriptions."""
    if not descriptions:
        return None
    try:
        vectorizer = TfidfVectorizer(min_df=1, stop_words="english")
        matrix = vectorizer.fit_transform(descriptions)
        return matrix
    except Exception:
        return None


def determine_match_state(carrier: Optional[dict], pa: Optional[dict], confidence: float) -> str:
    """Determine the match state for a pair."""
    if carrier is None:
        return "missing_from_carrier"
    if pa is None:
        return "only_in_carrier"

    if confidence < 0.55:
        return "unresolved"

    # Compare qty, unit_price, rcv
    qty_delta_pct = 0.0
    price_delta_pct = 0.0
    if carrier.get("qty", 0) and pa.get("qty", 0):
        qty_delta_pct = abs(carrier["qty"] - pa["qty"]) / max(pa["qty"], 0.001)
    if carrier.get("unit_price", 0) and pa.get("unit_price", 0):
        price_delta_pct = abs(carrier["unit_price"] - pa["unit_price"]) / max(pa["unit_price"], 0.001)

    if qty_delta_pct > 0.01 and price_delta_pct > 0.01:
        return "scope_diff"
    if qty_delta_pct > 0.01:
        return "qty_diff"
    if price_delta_pct > 0.01:
        return "price_diff"

    return "exact_match"


def match_estimates(carrier_items: list, pa_items: list) -> list[dict]:
    """
    Three-tier matching engine. Returns list of match dicts.
    """
    matches = []
    used_carrier_ids = set()
    used_pa_ids = set()

    # Add indices for identification
    for i, item in enumerate(carrier_items):
        item["_idx"] = i
    for i, item in enumerate(pa_items):
        item["_idx"] = i

    # --- Tier 1: Exact code match ---
    tier1_pa_remaining = []
    for pa in pa_items:
        pa_cat = pa.get("category_code")
        pa_sel = pa.get("selector_code")
        pa_act = pa.get("activity_code")
        pa_room = (pa.get("room_name") or "general").lower()

        if not pa_cat or not pa_sel or not pa_act:
            tier1_pa_remaining.append(pa)
            continue

        best_carrier = None
        for carrier in carrier_items:
            if carrier["_idx"] in used_carrier_ids:
                continue
            if (
                carrier.get("category_code") == pa_cat
                and carrier.get("selector_code") == pa_sel
                and carrier.get("activity_code") == pa_act
            ):
                c_room = (carrier.get("room_name") or "general").lower()
                if c_room == pa_room or pa_room == "general" or c_room == "general":
                    best_carrier = carrier
                    break

        if best_carrier is not None:
            used_carrier_ids.add(best_carrier["_idx"])
            used_pa_ids.add(pa["_idx"])
            state = determine_match_state(best_carrier, pa, 1.0)
            matches.append({
                "carrier_item": best_carrier,
                "pa_item": pa,
                "match_type": "exact",
                "match_state": state,
                "confidence": 1.0,
                "qty_delta": pa.get("qty", 0) - best_carrier.get("qty", 0),
                "unit_price_delta": pa.get("unit_price", 0) - best_carrier.get("unit_price", 0),
                "rcv_delta": pa.get("rcv", 0) - best_carrier.get("rcv", 0),
                "score_breakdown": json.dumps({"tier": 1, "code_match": True}),
            })
        else:
            tier1_pa_remaining.append(pa)

    # --- Tier 2: Fuzzy match ---
    remaining_carriers = [c for c in carrier_items if c["_idx"] not in used_carrier_ids]
    tier2_pa_remaining = []

    # Build cost matrix for fuzzy matching
    if tier1_pa_remaining and remaining_carriers:
        n_pa = len(tier1_pa_remaining)
        n_carrier = len(remaining_carriers)
        score_matrix = np.zeros((n_pa, n_carrier))

        for i, pa in enumerate(tier1_pa_remaining):
            pa_desc = pa.get("description_normalized") or ""
            for j, carrier in enumerate(remaining_carriers):
                c_desc = carrier.get("description_normalized") or ""
                desc_sim = fuzz.token_set_ratio(pa_desc, c_desc) / 100.0
                if desc_sim < 0.4:
                    continue
                code_sim = code_similarity(pa, carrier)
                qty_prox = qty_proximity(pa, carrier)
                unit_m = unit_match(pa, carrier)
                room_m = room_similarity(pa, carrier)

                combined = (
                    code_sim * 0.45
                    + desc_sim * 0.30
                    + qty_prox * 0.10
                    + unit_m * 0.10
                    + room_m * 0.05
                )
                score_matrix[i, j] = combined

        # Use Hungarian algorithm for optimal assignment
        # We want to maximize score, so negate for minimization
        cost_matrix = 1.0 - score_matrix
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        fuzzy_assigned_pa = set()
        fuzzy_assigned_carrier = set()

        for r, c in zip(row_ind, col_ind):
            score = score_matrix[r, c]
            if score >= 0.40:  # minimum threshold for fuzzy
                pa = tier1_pa_remaining[r]
                carrier = remaining_carriers[c]
                fuzzy_assigned_pa.add(r)
                fuzzy_assigned_carrier.add(c)
                used_carrier_ids.add(carrier["_idx"])
                used_pa_ids.add(pa["_idx"])

                pa_desc = pa.get("description_normalized") or ""
                c_desc = carrier.get("description_normalized") or ""
                desc_sim = fuzz.token_set_ratio(pa_desc, c_desc) / 100.0
                code_sim = code_similarity(pa, carrier)

                confidence = min(score, 1.0)
                match_type = "fuzzy" if score >= 0.55 else "semantic"
                state = determine_match_state(carrier, pa, confidence)

                matches.append({
                    "carrier_item": carrier,
                    "pa_item": pa,
                    "match_type": match_type,
                    "match_state": state,
                    "confidence": confidence,
                    "qty_delta": pa.get("qty", 0) - carrier.get("qty", 0),
                    "unit_price_delta": pa.get("unit_price", 0) - carrier.get("unit_price", 0),
                    "rcv_delta": pa.get("rcv", 0) - carrier.get("rcv", 0),
                    "score_breakdown": json.dumps({
                        "tier": 2,
                        "combined": score,
                        "desc_sim": desc_sim,
                        "code_sim": code_sim,
                    }),
                })

        tier2_pa_remaining = [
            pa for i, pa in enumerate(tier1_pa_remaining) if i not in fuzzy_assigned_pa
        ]
        remaining_carriers = [
            c for j, c in enumerate(remaining_carriers) if j not in fuzzy_assigned_carrier
        ]
    else:
        tier2_pa_remaining = tier1_pa_remaining

    # --- Tier 3: TF-IDF semantic fallback ---
    if tier2_pa_remaining and remaining_carriers:
        all_descs = (
            [pa.get("description_normalized") or "" for pa in tier2_pa_remaining]
            + [c.get("description_normalized") or "" for c in remaining_carriers]
        )
        try:
            vectorizer = TfidfVectorizer(min_df=1, stop_words="english")
            tfidf_matrix = vectorizer.fit_transform(all_descs)
            n_pa = len(tier2_pa_remaining)
            pa_vecs = tfidf_matrix[:n_pa]
            carrier_vecs = tfidf_matrix[n_pa:]

            sim_matrix = cosine_similarity(pa_vecs, carrier_vecs)
            cost_matrix = 1.0 - sim_matrix
            row_ind, col_ind = linear_sum_assignment(cost_matrix)

            sem_assigned_pa = set()
            sem_assigned_carrier = set()

            for r, c in zip(row_ind, col_ind):
                score = sim_matrix[r, c]
                if score >= 0.30:  # minimum semantic threshold
                    pa = tier2_pa_remaining[r]
                    carrier = remaining_carriers[c]
                    sem_assigned_pa.add(r)
                    sem_assigned_carrier.add(c)
                    used_carrier_ids.add(carrier["_idx"])
                    used_pa_ids.add(pa["_idx"])

                    confidence = score * 0.65  # semantic is less reliable
                    state = determine_match_state(carrier, pa, confidence)
                    matches.append({
                        "carrier_item": carrier,
                        "pa_item": pa,
                        "match_type": "semantic",
                        "match_state": state,
                        "confidence": confidence,
                        "qty_delta": pa.get("qty", 0) - carrier.get("qty", 0),
                        "unit_price_delta": pa.get("unit_price", 0) - carrier.get("unit_price", 0),
                        "rcv_delta": pa.get("rcv", 0) - carrier.get("rcv", 0),
                        "score_breakdown": json.dumps({"tier": 3, "tfidf_sim": score}),
                    })

            tier2_pa_remaining = [
                pa for i, pa in enumerate(tier2_pa_remaining) if i not in sem_assigned_pa
            ]
            remaining_carriers = [
                c for j, c in enumerate(remaining_carriers) if j not in sem_assigned_carrier
            ]
        except Exception as e:
            logger.warning(f"Semantic matching failed: {e}")

    # Unmatched PA items
    for pa in tier2_pa_remaining:
        if pa["_idx"] not in used_pa_ids:
            matches.append({
                "carrier_item": None,
                "pa_item": pa,
                "match_type": "unmatched",
                "match_state": "missing_from_carrier",
                "confidence": 0.0,
                "qty_delta": pa.get("qty", 0),
                "unit_price_delta": pa.get("unit_price", 0),
                "rcv_delta": pa.get("rcv", 0),
                "score_breakdown": json.dumps({"tier": "unmatched"}),
            })

    # Unmatched carrier items
    for carrier in remaining_carriers:
        if carrier["_idx"] not in used_carrier_ids:
            matches.append({
                "carrier_item": carrier,
                "pa_item": None,
                "match_type": "unmatched",
                "match_state": "only_in_carrier",
                "confidence": 0.0,
                "qty_delta": -carrier.get("qty", 0),
                "unit_price_delta": -carrier.get("unit_price", 0),
                "rcv_delta": -carrier.get("rcv", 0),
                "score_breakdown": json.dumps({"tier": "unmatched"}),
            })

    return matches
