"""
Lead value estimation + temperature classification.

Maps a lead's requested service to the business's real price ranges
(business_data.json), with keyword fallbacks for services not listed.
Used by the owner SMS (the "money feature") and hot-lead detection.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

# Fallbacks when the service doesn't match business_data services.
_FALLBACK_RANGES: list[tuple[re.Pattern, Tuple[int, int]]] = [
    (re.compile(r"ceramic|coating", re.I), (800, 1500)),
    (re.compile(r"paint\s*correction|polish", re.I), (400, 1200)),
    (re.compile(r"ppf|clear\s*bra|film", re.I), (1500, 3500)),
    (re.compile(r"wrap", re.I), (2000, 4000)),
    (re.compile(r"tint", re.I), (350, 600)),
    (re.compile(r"full\s*detail", re.I), (180, 350)),
    (re.compile(r"interior", re.I), (150, 220)),
    (re.compile(r"wash|exterior", re.I), (50, 150)),
]

HIGH_VALUE_THRESHOLD = 1000


def estimate_value(
    lead: Dict[str, Any],
    business_data: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[int, int]]:
    """Return (min, max) estimated dollar value for the lead's service, or None."""
    service = lead.get("service_requested")
    if not service:
        return None
    s = service.lower()

    for svc in (business_data or {}).get("services", []) or []:
        name = (svc.get("name") or "").lower()
        if not name:
            continue
        if (name in s or s in name) and svc.get("price_min") and svc.get("price_max"):
            return int(svc["price_min"]), int(svc["price_max"])

    for pattern, rng in _FALLBACK_RANGES:
        if pattern.search(s):
            return rng
    return None


def format_value(rng: Optional[Tuple[int, int]]) -> Optional[str]:
    if not rng:
        return None
    return f"${rng[0]:,}\u2013${rng[1]:,}"


def lead_temperature(
    lead: Dict[str, Any],
    business_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Classify the lead: "hot", "warm", or "new".

    hot  = high estimated value AND urgency signal, or explicit urgency + phone
    warm = service + vehicle identified (a real, actionable enquiry)
    new  = anything else
    """
    rng = estimate_value(lead, business_data)
    high_value = bool(rng and rng[1] >= HIGH_VALUE_THRESHOLD)
    urgent = (lead.get("urgency") or "").lower() in {"urgent", "soon", "asap", "today"}

    if (high_value and urgent) or (urgent and lead.get("customer_phone")):
        return "hot"
    if lead.get("service_requested") and (lead.get("vehicle_make") or lead.get("vehicle_model")):
        return "warm"
    return "new"


def recommended_next_step(
    lead: Dict[str, Any],
    business_data: Optional[Dict[str, Any]] = None,
) -> str:
    """One-line action suggestion for the owner SMS."""
    temp = lead_temperature(lead, business_data)
    service = (lead.get("service_requested") or "").lower()
    when = lead.get("preferred_date") or ""

    needs_inspection = bool(
        re.search(r"ceramic|coating|correction|ppf", service)
        or re.search(r"swirl|scratch|oxidat|water\s*spot", lead.get("condition_notes") or "", re.I)
    )

    if temp == "hot":
        return "Call back ASAP — customer signaled urgency."
    if needs_inspection:
        return "Call back today and offer an inspection slot."
    if when:
        return f"Confirm the {when} appointment by text or call."
    if not lead.get("customer_phone"):
        return "No callback number captured — check transcript for contact info."
    return "Call or text back to confirm details and book."
