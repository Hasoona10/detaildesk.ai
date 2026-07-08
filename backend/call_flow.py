"""
Conversation flow for the auto-detailing AI receptionist.

This module is the brain of every customer-facing channel (phone, widget, HTTP).
For every customer turn it:

1. Classifies intent (ML → rule → LLM fallback via `intents.classify_intent`).
2. Uses a single LLM call to BOTH generate the receptionist reply AND extract
   structured lead slots (name, phone, vehicle, service, preferred time, etc.).
3. Persists the in-progress lead to `leads_log.json` after each turn.
4. When the lead becomes "qualified" (has contact info + intent), fires a
   one-time Twilio SMS summary to the owner.

It's intentionally MVP-shaped: no DB, no kitchen tickets, no menu parsing, no
complex order math. Just structured lead capture + light template fast paths
for cheap/common questions (hours, location, service area).

Backward-compatible names kept for the rest of the codebase:
- ConversationState, get_conversation, clear_conversation, process_customer_message
- ORDERS_LOG_PATH (now aliased to LEADS_LOG_PATH for any legacy callers)
- log_order (now logs a lead/turn for any legacy callers)
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils.logger import logger
from .intents import Intent, classify_intent
from .rag import get_rag_system, load_business_data
from .lead_store import (
    LEADS_LOG_PATH,
    append_transcript,
    is_qualified,
    merge_lead,
    new_lead,
    save_lead,
)
from .sms_notify import notify_owner

# Legacy alias - main.py and friends used to import ORDERS_LOG_PATH from here.
ORDERS_LOG_PATH = LEADS_LOG_PATH

# ---------------------------------------------------------------------------
# Business data (loaded once for fast-path answers)
# ---------------------------------------------------------------------------

BUSINESS_DATA_PATH = Path(__file__).parent / "business_data.json"
try:
    BUSINESS_DATA: Dict[str, Any] = load_business_data(BUSINESS_DATA_PATH)
except Exception as e:
    logger.error(f"Failed to load business data: {e}")
    BUSINESS_DATA = {}


def _business_name() -> str:
    return BUSINESS_DATA.get("business_name", "the shop")


def _short_name() -> str:
    return BUSINESS_DATA.get("short_name") or _business_name()


def _persona_name() -> str:
    persona = BUSINESS_DATA.get("ai_persona") or {}
    return persona.get("assistant_name", "Riley")


# ---------------------------------------------------------------------------
# Conversation state
# ---------------------------------------------------------------------------


class ConversationState:
    """In-memory state for a single call/chat session.

    Each session owns one `lead` dict (see `lead_store.new_lead`) that we
    progressively fill in as the conversation goes.
    """

    def __init__(self, call_sid: str, business_id: str = "oc_elite_detailing"):
        self.call_sid = call_sid
        self.business_id = business_id
        self.messages: List[Dict[str, Any]] = []
        self.current_intent: Optional[Intent] = None
        self.lead: Dict[str, Any] = new_lead(business_id=business_id, call_sid=call_sid)
        self.lead["channel"] = _detect_channel(call_sid)
        # For SMS, the sender's phone is already known from the session id,
        # so prepopulate the lead's customer_phone slot.
        if self.lead["channel"] == "sms":
            phone = _extract_phone_from_sms_session(call_sid)
            if phone:
                self.lead["customer_phone"] = phone
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })
        self.updated_at = datetime.utcnow()
        append_transcript(self.lead, role=role, text=content)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_sid": self.call_sid,
            "business_id": self.business_id,
            "messages": self.messages,
            "current_intent": self.current_intent.value if self.current_intent else None,
            "lead": self.lead,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


def _detect_channel(session_id: str) -> str:
    """Infer channel from the session id prefix.

    - Twilio voice call SIDs start with "CA" (or our test prefix "call_")
    - Inbound SMS session ids are minted as `sms_{from_number}` by
      `twilio_sms_handler._sms_session_id`
    - Anything else (`web_*`, `ws_*`, ad-hoc) is treated as chat
    """
    if session_id.startswith("sms_"):
        return "sms"
    if session_id.startswith(("CA", "call_")):
        return "phone"
    return "chat"


def _extract_phone_from_sms_session(session_id: str) -> Optional[str]:
    """Pull the sender's phone out of a `sms_+17145551234` style session id."""
    if not session_id.startswith("sms_"):
        return None
    phone = session_id[len("sms_"):].strip()
    return phone or None


conversations: Dict[str, ConversationState] = {}


def get_conversation(call_sid: str, business_id: str = "oc_elite_detailing") -> ConversationState:
    if call_sid not in conversations:
        conversations[call_sid] = ConversationState(call_sid, business_id)
        logger.info(f"Created new conversation for session: {call_sid}")
    return conversations[call_sid]


def clear_conversation(call_sid: str) -> None:
    if call_sid in conversations:
        # Persist final snapshot of the lead before forgetting it
        try:
            save_lead(conversations[call_sid].lead)
        except Exception as e:
            logger.error(f"Failed to persist lead on clear: {e}")
        del conversations[call_sid]
        logger.info(f"Cleared conversation: {call_sid}")


# ---------------------------------------------------------------------------
# Lightweight regex-based slot extraction (cheap pre-pass before the LLM call)
# ---------------------------------------------------------------------------

PHONE_RE = re.compile(r"(?:\+?1[\s\-.])?\(?(\d{3})\)?[\s\-.]?(\d{3})[\s\-.]?(\d{4})")
NAME_RE = re.compile(
    r"\b(?:my name is|i'm|i am|this is|it's|its)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(19[8-9]\d|20[0-3]\d)\b")

KNOWN_MAKES = {
    "tesla", "bmw", "mercedes", "mercedes-benz", "audi", "porsche", "ferrari",
    "lamborghini", "lexus", "infiniti", "acura", "honda", "toyota", "nissan",
    "ford", "chevy", "chevrolet", "gmc", "dodge", "ram", "jeep", "subaru",
    "mazda", "hyundai", "kia", "volkswagen", "vw", "volvo", "land rover",
    "range rover", "jaguar", "cadillac", "lincoln", "buick", "mini", "fiat",
    "alfa romeo", "genesis", "rivian", "lucid",
}

KNOWN_COLORS = {
    "black", "white", "silver", "gray", "grey", "red", "blue", "green",
    "yellow", "orange", "purple", "brown", "tan", "beige", "gold",
    "champagne", "pearl",
}

SERVICE_KEYWORDS = {
    "interior detail": "Interior Detail",
    "interior": "Interior Detail",
    "exterior detail": "Exterior Detail",
    "exterior": "Exterior Detail",
    "full detail": "Full Detail",
    "full": "Full Detail",
    "paint correction": "Paint Correction",
    "correction": "Paint Correction",
    "polish": "Paint Correction",
    "ceramic coating": "Ceramic Coating",
    "ceramic": "Ceramic Coating",
    "coating": "Ceramic Coating",
    "maintenance wash": "Maintenance Wash",
    "wash": "Maintenance Wash",
}


def _regex_extract(text: str) -> Dict[str, Any]:
    """Cheap pre-pass for obvious slots the LLM might also catch."""
    found: Dict[str, Any] = {}
    text_lower = text.lower()

    m = PHONE_RE.search(text)
    if m:
        found["customer_phone"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    m = NAME_RE.search(text)
    if m:
        found["customer_name"] = m.group(1).strip().title()

    m = YEAR_RE.search(text)
    if m:
        found["vehicle_year"] = m.group(1)

    for make in KNOWN_MAKES:
        if re.search(rf"\b{re.escape(make)}\b", text_lower):
            found["vehicle_make"] = make.title()
            break

    for color in KNOWN_COLORS:
        if re.search(rf"\b{color}\b", text_lower):
            found["vehicle_color"] = color
            break

    for kw, label in SERVICE_KEYWORDS.items():
        if kw in text_lower:
            found["service_requested"] = label
            break

    if "mobile" in text_lower or "come to" in text_lower or "at my" in text_lower:
        found["mobile_or_shop_preference"] = "mobile"
    elif "shop" in text_lower or "bring it in" in text_lower or "drop off" in text_lower:
        found["mobile_or_shop_preference"] = "shop"

    if any(w in text_lower for w in ["today", "tonight", "asap", "urgent", "as soon as", "right away"]):
        found["urgency"] = "urgent"
    elif "tomorrow" in text_lower:
        found["urgency"] = "soon"

    # Paint/interior condition mentions — keep the raw sentence as notes so the
    # structured workflows (and owner SMS) get real condition info even when
    # running without the LLM.
    if re.search(
        r"swirl|scratch|water\s*spot|oxidat|fade|peel|pet\s*hair|dog\s*hair|stain|"
        r"spill|smoke|odor|smell|sap|tar|overspray|hard\s*water",
        text_lower,
    ):
        found["condition_notes"] = text.strip()[:200]

    return found


# ---------------------------------------------------------------------------
# Structured service workflows
#
# The AI is a lead intake assistant, not a genius chatbot. Once we know what
# service the caller wants, we follow a detailer-specific checklist: ask the
# right questions, in the right order, one at a time. These checklists drive
# both the LLM system prompt and the no-LLM deterministic fallback.
# ---------------------------------------------------------------------------

SERVICE_FLOWS: List[Dict[str, Any]] = [
    {
        "id": "ceramic_coating",
        "match": re.compile(r"ceramic|coating", re.I),
        "checklist": [
            ("vehicle_make", "What's the year, make, and model of the vehicle?"),
            ("condition_notes", "How's the paint looking — any swirl marks, scratches, or water spots you've noticed?"),
            ("preferred_date", "When were you hoping to get it done?"),
            ("customer_name", "And what's your name?"),
            ("customer_phone", "What's the best number to reach you at?"),
        ],
        "talking_points": (
            "Ceramic coating boosts gloss and makes maintenance much easier, but it is NOT scratch-proof. "
            "If the paint has swirls or scratches, paint correction is usually recommended first. "
            "Final quote depends on the vehicle and paint condition — the team confirms after an inspection."
        ),
    },
    {
        "id": "paint_correction",
        "match": re.compile(r"paint\s*correction|correction|polish|buff", re.I),
        "checklist": [
            ("vehicle_make", "What's the year, make, and model?"),
            ("vehicle_color", "What color is the paint? (Dark colors like black show swirls the most.)"),
            ("condition_notes", "What are we dealing with — swirl marks, scratches, oxidation, water spots?"),
            ("preferred_date", "Want to set up a quick inspection so we can quote it accurately? What day works?"),
            ("customer_name", "What's your name?"),
            ("customer_phone", "And the best number to reach you?"),
        ],
        "talking_points": (
            "Paint correction pricing depends on paint condition, color, and vehicle size. "
            "Soft or black paint takes more care. An in-person inspection gets them an exact quote."
        ),
    },
    {
        "id": "full_detail",
        "match": re.compile(r"full\s*detail|interior|exterior|detail", re.I),
        "checklist": [
            ("vehicle_make", "What kind of vehicle is it — year, make, and model?"),
            ("condition_notes", "Anything specific inside or out — pet hair, stains, heavy dirt?"),
            ("mobile_or_shop_preference", "Would you like us to come to you, or would you rather drop it at the shop?"),
            ("preferred_date", "What day and time works best?"),
            ("customer_name", "What's your name?"),
            ("customer_phone", "And the best phone number for you?"),
        ],
        "talking_points": (
            "Clarify whether they want interior, exterior, or full. Pet hair and stain removal can add time/cost."
        ),
    },
    {
        "id": "mobile_detail",
        "match": re.compile(r"mobile|come\s*to\s*me|at\s*my\s*(house|home|place|office|work)", re.I),
        "checklist": [
            ("customer_location", "What city are you in? We cover about 25 miles around Santa Ana."),
            ("condition_notes", "Is there access to water and power where the vehicle is, or should we bring our own?"),
            ("vehicle_make", "What vehicle are we detailing — year, make, and model?"),
            ("preferred_date", "What day and time works for you?"),
            ("customer_name", "What's your name?"),
            ("customer_phone", "Best number to reach you at?"),
        ],
        "talking_points": (
            "Mobile service needs a safe place to park; we can bring water/power if the location doesn't have it. "
            "If they're outside the ~25-mile radius, capture the lead and say the team will confirm."
        ),
    },
]


def _active_flow(lead: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pick the structured workflow matching the lead's requested service."""
    service = lead.get("service_requested") or ""
    if lead.get("mobile_or_shop_preference") == "mobile" and not service:
        return next(f for f in SERVICE_FLOWS if f["id"] == "mobile_detail")
    if not service:
        return None
    for flow in SERVICE_FLOWS:
        if flow["match"].search(service):
            return flow
    return None


def _flow_missing_questions(flow: Dict[str, Any], lead: Dict[str, Any]) -> List[str]:
    """Ordered list of checklist questions whose slot is still empty."""
    return [q for slot, q in flow["checklist"] if not lead.get(slot)]


# ---------------------------------------------------------------------------
# Escalation rules
#
# The AI should know when to stop selling and hand off. These are cheap
# keyword rules that run BEFORE the LLM so an angry caller never gets a
# chirpy upsell.
# ---------------------------------------------------------------------------

_ANGRY_RE = re.compile(
    r"\b(angry|furious|pissed|unacceptable|terrible|awful|worst|ripped\s*off|"
    r"refund|complaint|complain|damaged\s+my|ruined|scratched\s+my|sue|lawyer|bbb)\b",
    re.I,
)
_HUMAN_RE = re.compile(
    r"\b(real\s+person|a\s+human|actual\s+person|"
    r"(speak|talk)\s+(to|with)\s+(someone|somebody|the\s+owner|a\s+manager|the\s+manager)|"
    r"is\s+the\s+owner\s+there|are\s+you\s+a\s+(robot|bot|machine)|stop\s+the\s+robot)\b",
    re.I,
)


def _check_escalation(text: str, conversation: "ConversationState") -> Optional[str]:
    """Return a templated de-escalation/handoff reply, or None if no rule fires.

    Side effects: flags the lead so it surfaces as urgent/hot and triggers an
    owner notification as soon as we have any contact info.
    """
    lead = conversation.lead
    biz = _business_name()

    if _ANGRY_RE.search(text):
        lead["urgency"] = "urgent"
        lead["escalation"] = "upset_customer"
        if not lead.get("condition_notes"):
            lead["condition_notes"] = f"ESCALATION - customer upset: \"{text[:140]}\""
        if lead.get("customer_phone"):
            return (
                "I'm really sorry about that — I want to make sure this gets handled right. "
                f"I'm flagging this for the owner of {biz} right now, and someone will call you back "
                "as soon as possible. Is there anything else you'd like me to pass along?"
            )
        return (
            "I'm really sorry about that — I want to make sure this gets handled right. "
            "Let me flag this for the owner so they can call you back personally. "
            "What's the best number to reach you at?"
        )

    if _HUMAN_RE.search(text):
        lead["escalation"] = lead.get("escalation") or "human_requested"
        if lead.get("customer_phone"):
            return (
                "Totally understand — I'll have someone from the team call you back shortly at "
                f"{lead['customer_phone']}. Anything you'd like me to pass along so they're ready for you?"
            )
        return (
            "Totally understand — I'm the after-hours assistant, but I can have someone from the "
            "team call you back shortly. What's the best number to reach you at?"
        )

    return None


# ---------------------------------------------------------------------------
# Fast-path templated answers (zero LLM cost for cheap, common questions)
# ---------------------------------------------------------------------------


def _format_hours() -> str:
    hours = BUSINESS_DATA.get("hours", {})
    if not hours:
        return ""
    grouped: List[str] = []
    for day, time in hours.items():
        grouped.append(f"{day.capitalize()}: {time}")
    return "; ".join(grouped)


def _fast_answer(intent: Intent, text: str) -> Optional[str]:
    """Return a templated response for intents that don't need the LLM."""
    biz = _business_name()
    short = _short_name()

    if intent == Intent.ASK_HOURS:
        hours_text = _format_hours()
        if hours_text:
            return (
                f"Our hours at {short} are: {hours_text}. "
                "Want me to grab some quick details so we can line up an appointment?"
            )

    if intent == Intent.ASK_LOCATION:
        addr = BUSINESS_DATA.get("address", {}) or {}
        street = addr.get("street")
        city = addr.get("city")
        state = addr.get("state")
        zip_ = addr.get("zip")
        if street and city:
            return (
                f"We're at {street}, {city}, {state} {zip_}. We also offer mobile detailing "
                "in much of Orange County — want me to check if we cover your area?"
            )

    if intent == Intent.ASK_SERVICE_AREA:
        mobile = BUSINESS_DATA.get("mobile_service", {}) or {}
        if mobile.get("available"):
            areas = ", ".join(mobile.get("service_area_examples", []) or [])
            radius = mobile.get("service_radius_miles", 25)
            return (
                f"Yep — we do mobile detailing within about {radius} miles of Santa Ana. "
                f"That covers most of OC including {areas}. What city are you in?"
            )

    if intent == Intent.ASK_MOBILE_SERVICE:
        mobile = BUSINESS_DATA.get("mobile_service", {}) or {}
        if mobile.get("available"):
            radius = mobile.get("service_radius_miles", 25)
            return (
                f"Yes, we come to you. Mobile service runs about {radius} miles around Santa Ana, "
                "and we just need a safe place to park and ideally water/power (we can bring our own if not). "
                "What city are you in, and what vehicle are we helping you with?"
            )

    if intent == Intent.ASK_SERVICES:
        services = BUSINESS_DATA.get("services", []) or []
        if services:
            names = ", ".join(svc.get("name", "") for svc in services if svc.get("name"))
            return (
                f"We offer {names}. Which one sounds closest to what you need? "
                "If you're not sure, I can walk you through it."
            )

    if intent == Intent.GREETING:
        return (
            f"Hey, thanks for reaching out to {biz}! "
            "What vehicle are we helping you with today, and what kind of detail are you thinking?"
        )

    if intent == Intent.GOODBYE:
        return f"Awesome — thanks for reaching out to {biz}. We'll be in touch shortly. Take care!"

    return None


# ---------------------------------------------------------------------------
# Main LLM-driven turn: response + structured lead extraction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """You are {assistant_name}, the AI receptionist for {business_name}, an auto detailing business in Orange County, CA.

Your job on every customer turn is to do TWO things at once:
1. Reply naturally to the customer (one short paragraph, friendly and confident).
2. Extract any new lead information they revealed in this turn.

CORE BEHAVIOR:
- Always be trying to capture: name, phone number, vehicle (year/make/model/color), service they want, paint/interior condition notes, mobile vs shop preference, customer city/location, preferred date/time, urgency.
- Ask AT MOST one new question per reply, and only ask for info we don't already have.
- Reference the captured slots so you don't ask the same thing twice.
- If they ask about ceramic coating: explain it protects gloss/makes maintenance easier but is NOT scratch-proof, and that paint correction may be recommended first if there are swirl marks or scratches.
- If they ask about paint correction: explain price depends on paint condition, color, and vehicle size; offer to inspect.
- If they ask about pricing for paint correction or ceramic coating, give the RANGE from the services list and say the team confirms the exact quote after seeing the vehicle.
- Never promise scratch removal or that ceramic coating prevents all scratches.
- Never book outside business hours; never confirm a mobile booking outside the 25-mile radius (collect the lead and say the team will confirm).
- If something is uncertain, capture the lead and say the team will follow up.

CURRENTLY KNOWN ABOUT THIS LEAD (don't re-ask these):
{known_slots}

{workflow}
BUSINESS CONTEXT YOU CAN USE:
{business_context}

You MUST respond in this exact JSON shape and nothing else:
{{
  "reply": "<your message to the customer>",
  "updates": {{
    "customer_name": null,
    "customer_phone": null,
    "vehicle_year": null,
    "vehicle_make": null,
    "vehicle_model": null,
    "vehicle_color": null,
    "service_requested": null,
    "condition_notes": null,
    "mobile_or_shop_preference": null,
    "customer_location": null,
    "preferred_date": null,
    "preferred_time": null,
    "urgency": null,
    "budget_signal": null,
    "lead_summary": null
  }},
  "qualified": false
}}

Rules for the JSON:
- Only fill in fields you learned from THIS turn or earlier turns. Leave the rest null.
- "lead_summary": a one-sentence summary of what the customer wants, suitable for an SMS to the owner.
- "qualified": true once we have a phone number OR name plus at least one of: service_requested, vehicle_make, or preferred_date.
"""


def _build_business_context() -> str:
    services = BUSINESS_DATA.get("services", []) or []
    svc_lines = []
    for s in services:
        pmin = s.get("price_min")
        pmax = s.get("price_max")
        price_str = f" (${pmin}-${pmax})" if pmin and pmax else ""
        svc_lines.append(f"- {s.get('name','')}{price_str}: {s.get('description','')}")

    hours_text = _format_hours()
    mobile = BUSINESS_DATA.get("mobile_service", {}) or {}
    radius = mobile.get("service_radius_miles", 25)
    areas = ", ".join(mobile.get("service_area_examples", []) or [])

    return (
        "Services:\n"
        + "\n".join(svc_lines)
        + f"\n\nHours: {hours_text}"
        + f"\nMobile service radius: ~{radius} miles around Santa Ana, including {areas}."
    )


def _format_known_slots(lead: Dict[str, Any]) -> str:
    rows: List[str] = []
    for key in (
        "customer_name", "customer_phone",
        "vehicle_year", "vehicle_make", "vehicle_model", "vehicle_color",
        "service_requested", "condition_notes",
        "mobile_or_shop_preference", "customer_location",
        "preferred_date", "preferred_time", "urgency", "budget_signal",
    ):
        val = lead.get(key)
        if val:
            rows.append(f"- {key}: {val}")
    return "\n".join(rows) if rows else "(nothing captured yet)"


def _build_workflow_block(lead: Dict[str, Any]) -> str:
    """Inject the active structured workflow into the system prompt."""
    flow = _active_flow(lead)
    if not flow:
        return ""
    missing = _flow_missing_questions(flow, lead)
    if not missing:
        return (
            f"ACTIVE WORKFLOW ({flow['id']}): all checklist info is captured. "
            "Confirm the details back to the customer and let them know the team will follow up.\n"
        )
    questions = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(missing))
    return (
        f"ACTIVE WORKFLOW ({flow['id']}): follow this checklist. Ask the NEXT unanswered "
        f"question below (only one per reply):\n{questions}\n"
        f"Key facts for this service: {flow['talking_points']}\n"
    )


def _build_messages(conversation: ConversationState, user_text: str) -> List[Dict[str, str]]:
    sys_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        assistant_name=_persona_name(),
        business_name=_business_name(),
        known_slots=_format_known_slots(conversation.lead),
        workflow=_build_workflow_block(conversation.lead),
        business_context=_build_business_context(),
    )
    msgs: List[Dict[str, str]] = [{"role": "system", "content": sys_prompt}]
    # Last few turns for short-term context.
    for m in conversation.messages[-8:]:
        role = "assistant" if m["role"] == "assistant" else "user"
        msgs.append({"role": role, "content": m["content"]})
    msgs.append({"role": "user", "content": user_text})
    return msgs


def _llm_turn(conversation: ConversationState, user_text: str) -> Dict[str, Any]:
    """Single LLM call returning {reply, updates, qualified}."""
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; using deterministic fallback reply")
        return _fallback_turn(conversation, user_text)

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=_build_messages(conversation, user_text),
            temperature=0.4,
            max_tokens=350,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        reply = (data.get("reply") or "").strip()
        updates = data.get("updates") or {}
        qualified = bool(data.get("qualified"))
        if not reply:
            return _fallback_turn(conversation, user_text)
        return {"reply": reply, "updates": updates, "qualified": qualified}
    except Exception as e:
        logger.error(f"LLM turn failed, falling back: {e}")
        return _fallback_turn(conversation, user_text)


def _fallback_turn(conversation: ConversationState, user_text: str) -> Dict[str, Any]:
    """Deterministic, LLM-free reply for demo / no-API-key environments.

    Follows the active service workflow's checklist if one matched, otherwise
    a generic lead-capture order.
    """
    lead = conversation.lead
    next_q = "Got it — anything else you want me to pass on to the team?"

    flow = _active_flow(lead)
    if flow:
        remaining = _flow_missing_questions(flow, lead)
        if remaining:
            next_q = remaining[0]
    else:
        missing = [
            ("service_requested", "Which service are you thinking — interior, exterior, full detail, paint correction, or ceramic coating?"),
            ("vehicle_make", "What's the year, make, and model of your vehicle?"),
            ("customer_name", "Sweet — what's your name?"),
            ("customer_phone", "What's the best phone number to reach you at?"),
            ("preferred_date", "When were you hoping to bring it in?"),
        ]
        for slot, question in missing:
            if not lead.get(slot):
                next_q = question
                break

    biz = _business_name()
    reply = f"Got it. {next_q}"
    if not conversation.messages:
        reply = (
            f"Hey, thanks for reaching out to {biz}! "
            "What vehicle are we helping you with today, and what kind of detail are you thinking?"
        )
    return {"reply": reply, "updates": {}, "qualified": False}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def process_customer_message(
    text: str,
    call_sid: str,
    business_id: str = "oc_elite_detailing",
) -> str:
    """Process a single customer message and return the AI's reply.

    Also updates the in-memory and on-disk lead, and fires the owner SMS
    the first time the lead becomes "qualified".
    """
    try:
        conversation = get_conversation(call_sid, business_id)
        conversation.add_message("user", text)

        # 1) Intent classification (used for fast paths + logging)
        intent = await classify_intent(text, method="auto")
        conversation.current_intent = intent

        # 2) Cheap regex pre-pass to grab obvious slots
        regex_updates = _regex_extract(text)
        if regex_updates:
            merge_lead(conversation.lead, regex_updates)

        # 3) Escalation rules run BEFORE any LLM/template logic: angry callers
        #    and "let me talk to a human" get a handoff, not a sales pitch.
        escalation_reply = _check_escalation(text, conversation)

        # 4) Fast-path templated answers (no LLM call needed) for cheap intents
        fast = escalation_reply or _fast_answer(intent, text)
        if escalation_reply:
            response_source = "escalation"
        elif fast:
            response_source = "template_fast_path"
        else:
            response_source = "llm_turn"

        if fast is not None:
            ai_reply = fast
            llm_updates: Dict[str, Any] = {}
            qualified_hint = False
        else:
            turn = _llm_turn(conversation, text)
            ai_reply = turn["reply"]
            llm_updates = turn.get("updates") or {}
            qualified_hint = bool(turn.get("qualified"))

        # 5) Merge LLM slot updates back into the lead
        if llm_updates:
            merge_lead(conversation.lead, llm_updates)

        # 6) Persist the lead and notify the owner once if newly qualified.
        #    Escalated leads with a phone number skip the qualification bar —
        #    the owner needs to know about an upset caller immediately.
        escalated_with_phone = bool(
            conversation.lead.get("escalation") and conversation.lead.get("customer_phone")
        )
        previously_notified = bool(conversation.lead.get("owner_notified"))
        if (
            qualified_hint or is_qualified(conversation.lead) or escalated_with_phone
        ) and not previously_notified:
            try:
                notify_result = notify_owner(conversation.lead, BUSINESS_DATA)
                sent = bool(notify_result.get("sent"))
                # Only mark notified when the SMS actually went out — a failed
                # send gets retried on the next qualified turn.
                conversation.lead["owner_notified"] = sent
                if sent:
                    conversation.lead["owner_notified_at"] = datetime.utcnow().isoformat() + "Z"
                conversation.lead["owner_notify_reason"] = notify_result.get("reason")
            except Exception as e:
                logger.error(f"notify_owner crashed: {e}")

        conversation.add_message("assistant", ai_reply)

        try:
            save_lead(conversation.lead)
        except Exception as e:
            logger.error(f"Failed to save lead: {e}")

        # 7) Record a per-turn log entry (used by the legacy /api/owner/orders endpoint)
        log_order(
            call_sid=call_sid,
            business_id=business_id,
            customer_text=text,
            ai_response=ai_reply,
            intent=intent,
            conversation=conversation,
            response_source=response_source,
        )

        return ai_reply

    except Exception as e:
        logger.error(f"Error in process_customer_message: {e}")
        # Reliability rule: even if the AI breaks mid-call, save whatever we
        # captured so far. The owner still gets a partial lead.
        try:
            conv = conversations.get(call_sid)
            if conv is not None:
                save_lead(conv.lead)
        except Exception as save_err:
            logger.error(f"Failed to save partial lead after error: {save_err}")
        return (
            "Sorry, I'm having trouble pulling that up. I'll send your info to the team "
            "so they can call you back. Could I grab your name and number just in case?"
        )


# ---------------------------------------------------------------------------
# Per-turn append-only log (kept JSON-compatible with legacy callers)
# ---------------------------------------------------------------------------

TURN_LOG_PATH = Path(__file__).parent / "turn_log.json"


def log_order(
    call_sid: str,
    business_id: str,
    customer_text: str,
    ai_response: str,
    intent: Optional[Intent] = None,
    conversation: Optional[ConversationState] = None,
    response_source: Optional[str] = None,
) -> None:
    """Append a structured turn record to `turn_log.json`.

    Name kept as `log_order` for backward compatibility with any old imports.
    """
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "call_sid": call_sid,
        "business_id": business_id,
        "intent": intent.value if intent else None,
        "customer_said": customer_text,
        "ai_response": ai_response,
        "response_source": response_source,
        "lead_id": conversation.lead.get("id") if conversation else None,
    }
    try:
        existing: List[Dict[str, Any]] = []
        if TURN_LOG_PATH.exists():
            try:
                with TURN_LOG_PATH.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    existing = loaded
            except Exception:
                existing = []
        existing.append(record)
        with TURN_LOG_PATH.open("w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to write turn log: {e}")
