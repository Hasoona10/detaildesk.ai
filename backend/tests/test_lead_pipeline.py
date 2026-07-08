"""Tests for the lead pipeline "money features":

- lead value estimation + temperature (lead_value.py)
- owner SMS summary format (sms_notify.build_owner_summary)
- structured service workflows (call_flow.SERVICE_FLOWS)
- escalation rules (call_flow._check_escalation)
"""
from __future__ import annotations

import pytest

from backend import call_flow
from backend.call_flow import ConversationState, _active_flow, _check_escalation, _flow_missing_questions
from backend.lead_value import estimate_value, format_value, lead_temperature, recommended_next_step
from backend.sms_notify import build_owner_summary

BUSINESS = {
    "services": [
        {"name": "Ceramic Coating", "price_min": 800, "price_max": 1500},
        {"name": "Full Detail", "price_min": 180, "price_max": 350},
    ]
}


def _lead(**kwargs) -> dict:
    base = {
        "id": "lead_test",
        "customer_name": None,
        "customer_phone": None,
        "vehicle_year": None,
        "vehicle_make": None,
        "vehicle_model": None,
        "vehicle_color": None,
        "service_requested": None,
        "condition_notes": None,
        "mobile_or_shop_preference": None,
        "customer_location": None,
        "preferred_date": None,
        "preferred_time": None,
        "urgency": None,
        "lead_summary": None,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Value estimation + temperature
# ---------------------------------------------------------------------------


def test_estimate_value_uses_business_prices():
    lead = _lead(service_requested="ceramic coating")
    assert estimate_value(lead, BUSINESS) == (800, 1500)


def test_estimate_value_falls_back_to_keywords():
    lead = _lead(service_requested="paint correction")
    rng = estimate_value(lead, BUSINESS)
    assert rng is not None and rng[1] >= 1000


def test_estimate_value_none_without_service():
    assert estimate_value(_lead(), BUSINESS) is None


def test_format_value():
    assert format_value((800, 1500)) == "$800\u2013$1,500"
    assert format_value(None) is None


def test_lead_temperature_hot_when_urgent_with_phone():
    lead = _lead(customer_phone="714-555-1234", urgency="urgent", service_requested="wash")
    assert lead_temperature(lead, BUSINESS) == "hot"


def test_lead_temperature_warm_with_service_and_vehicle():
    lead = _lead(service_requested="Full Detail", vehicle_make="Tesla")
    assert lead_temperature(lead, BUSINESS) == "warm"


def test_lead_temperature_new_otherwise():
    assert lead_temperature(_lead(), BUSINESS) == "new"


def test_recommended_next_step_inspection_for_coating():
    lead = _lead(service_requested="Ceramic Coating", customer_phone="714-555-1234")
    assert "inspection" in recommended_next_step(lead, BUSINESS).lower()


# ---------------------------------------------------------------------------
# Owner SMS format
# ---------------------------------------------------------------------------


def test_owner_summary_money_format():
    lead = _lead(
        customer_name="Mike Rodriguez",
        customer_phone="714-928-4731",
        vehicle_color="black",
        vehicle_make="Tesla",
        vehicle_model="Model 3",
        service_requested="Ceramic Coating",
        condition_notes="Swirl marks visible in sun",
        preferred_date="This weekend",
    )
    body = build_owner_summary(lead, BUSINESS)
    assert "Mike Rodriguez" in body
    assert "714-928-4731" in body
    assert "Vehicle: Black Tesla Model 3" in body
    assert "Service: Ceramic Coating" in body
    assert "Condition: Swirl marks visible in sun" in body
    assert "Timeline: This weekend" in body
    assert "Value: $800\u2013$1,500" in body
    assert "lead" in body.splitlines()[0].lower()  # header
    assert "Next step:" in body


def test_owner_summary_omits_empty_fields():
    body = build_owner_summary(_lead(customer_phone="714-555-0000"), BUSINESS)
    assert "Vehicle:" not in body
    assert "Condition:" not in body
    assert "Unknown caller" in body


# ---------------------------------------------------------------------------
# Structured workflows
# ---------------------------------------------------------------------------


def test_active_flow_matches_ceramic():
    lead = _lead(service_requested="ceramic coating")
    flow = _active_flow(lead)
    assert flow is not None and flow["id"] == "ceramic_coating"


def test_active_flow_mobile_without_service():
    lead = _lead(mobile_or_shop_preference="mobile")
    flow = _active_flow(lead)
    assert flow is not None and flow["id"] == "mobile_detail"


def test_flow_questions_shrink_as_slots_fill():
    lead = _lead(service_requested="ceramic coating")
    flow = _active_flow(lead)
    all_missing = _flow_missing_questions(flow, lead)
    lead["vehicle_make"] = "Tesla"
    lead["customer_phone"] = "714-555-1234"
    fewer = _flow_missing_questions(flow, lead)
    assert len(fewer) == len(all_missing) - 2


def test_no_flow_without_service():
    assert _active_flow(_lead()) is None


# ---------------------------------------------------------------------------
# Escalation rules
# ---------------------------------------------------------------------------


def _conversation() -> ConversationState:
    return ConversationState("call_test_escalation")


def test_angry_customer_gets_deescalation_and_urgent_flag():
    conv = _conversation()
    reply = _check_escalation("You guys scratched my hood, this is unacceptable!", conv)
    assert reply is not None
    assert "sorry" in reply.lower()
    assert conv.lead["urgency"] == "urgent"
    assert conv.lead["escalation"] == "upset_customer"


def test_human_request_offers_callback():
    conv = _conversation()
    reply = _check_escalation("Can I talk to a real person please?", conv)
    assert reply is not None
    assert "call you back" in reply.lower()
    assert conv.lead["escalation"] == "human_requested"


def test_normal_message_does_not_escalate():
    conv = _conversation()
    assert _check_escalation("How much is a full detail on a Honda Civic?", conv) is None
    assert _check_escalation("I'm the second owner of this car", conv) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
