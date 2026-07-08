"""
Lead model and simple JSON-file lead store for the AI detailing receptionist.

This is intentionally an MVP-grade store (single JSON file, in-process write lock)
so the demo runs with zero infrastructure. Swap for a real DB later.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils.logger import logger


LEADS_LOG_PATH = Path(__file__).parent / "leads_log.json"

# These are the canonical slots we try to capture for every detailing lead.
LEAD_SLOTS: tuple[str, ...] = (
    "customer_name",
    "customer_phone",
    "vehicle_year",
    "vehicle_make",
    "vehicle_model",
    "vehicle_color",
    "service_requested",
    "condition_notes",
    "mobile_or_shop_preference",
    "customer_location",
    "preferred_date",
    "preferred_time",
    "urgency",
    "budget_signal",
    "lead_summary",
)

VALID_STATUSES = {"new", "contacted", "booked", "lost", "resolved"}

_write_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def new_lead(business_id: str, call_sid: str | None = None) -> Dict[str, Any]:
    """Create a blank lead record with all standard slots set to None."""
    now = _now_iso()
    lead: Dict[str, Any] = {
        "id": f"lead_{uuid.uuid4().hex[:12]}",
        "business_id": business_id,
        "call_sid": call_sid,
        "channel": None,
        "status": "new",
        "ai_confidence": None,
        "owner_notified": False,
        "owner_notified_at": None,
        "transcript": [],
        "created_at": now,
        "updated_at": now,
    }
    for slot in LEAD_SLOTS:
        lead[slot] = None
    return lead


def is_qualified(lead: Dict[str, Any]) -> bool:
    """A 'qualified' lead is one we'd actually want to text the owner about.

    Rule: we need a contact handle (phone OR name) AND at least one of
    service_requested / vehicle_make / preferred_date so the owner has
    enough to follow up on.
    """
    has_contact = bool(lead.get("customer_phone")) or bool(lead.get("customer_name"))
    has_intent = (
        bool(lead.get("service_requested"))
        or bool(lead.get("vehicle_make"))
        or bool(lead.get("preferred_date"))
    )
    return has_contact and has_intent


def merge_lead(lead: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge non-empty slot updates into a lead, leaving existing values intact.

    Empty strings, None, and "unknown"-ish values are ignored so the LLM
    can't accidentally erase real captured slots.
    """
    if not updates:
        return lead
    for key, value in updates.items():
        if key not in LEAD_SLOTS and key not in {"lead_summary", "transcript", "channel", "status", "ai_confidence"}:
            continue
        if value is None:
            continue
        if isinstance(value, str):
            v = value.strip()
            if not v or v.lower() in {"unknown", "n/a", "none", "null"}:
                continue
            lead[key] = v
        else:
            lead[key] = value
    lead["updated_at"] = _now_iso()
    return lead


def append_transcript(lead: Dict[str, Any], role: str, text: str) -> None:
    """Append a single conversation turn to the lead transcript."""
    lead.setdefault("transcript", []).append({
        "role": role,
        "text": text,
        "ts": _now_iso(),
    })
    lead["updated_at"] = _now_iso()


def _read_all() -> List[Dict[str, Any]]:
    if not LEADS_LOG_PATH.exists():
        return []
    try:
        with LEADS_LOG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error(f"Failed to read leads log: {e}")
        return []


def _write_all(leads: List[Dict[str, Any]]) -> None:
    with _write_lock:
        try:
            with LEADS_LOG_PATH.open("w", encoding="utf-8") as f:
                json.dump(leads, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to write leads log: {e}")


def save_lead(lead: Dict[str, Any]) -> None:
    """Insert or update a lead by id."""
    leads = _read_all()
    for i, existing in enumerate(leads):
        if existing.get("id") == lead.get("id"):
            leads[i] = lead
            _write_all(leads)
            return
    leads.append(lead)
    _write_all(leads)


def list_leads(business_id: Optional[str] = None) -> List[Dict[str, Any]]:
    leads = _read_all()
    if business_id:
        leads = [l for l in leads if l.get("business_id") == business_id]
    leads.sort(key=lambda l: l.get("updated_at") or "", reverse=True)
    return leads


def get_lead(lead_id: str) -> Optional[Dict[str, Any]]:
    for lead in _read_all():
        if lead.get("id") == lead_id:
            return lead
    return None


def update_lead_status(lead_id: str, status: str) -> Optional[Dict[str, Any]]:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {sorted(VALID_STATUSES)}.")
    leads = _read_all()
    for i, lead in enumerate(leads):
        if lead.get("id") == lead_id:
            lead["status"] = status
            lead["updated_at"] = _now_iso()
            leads[i] = lead
            _write_all(leads)
            return lead
    return None
