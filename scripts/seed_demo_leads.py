#!/usr/bin/env python3
"""Seed `backend/leads_log.json` with realistic demo leads for the auto-detailing
AI receptionist.

Useful for demoing the Lead Inbox without having to make real phone calls.

Run from the project root:

    python scripts/seed_demo_leads.py            # append demo leads to leads_log.json
    python scripts/seed_demo_leads.py --replace  # wipe existing leads first
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Make `backend` importable when run from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.lead_store import (
    LEADS_LOG_PATH,
    LEAD_SLOTS,
    new_lead,
    save_lead,
)


BUSINESS_ID = "oc_elite_detailing"


def _ts(minutes_ago: int) -> str:
    return (datetime.utcnow() - timedelta(minutes=minutes_ago)).isoformat() + "Z"


def _build_lead(
    *,
    minutes_ago: int,
    customer_name: str,
    customer_phone: str,
    vehicle_year: str,
    vehicle_make: str,
    vehicle_model: str,
    vehicle_color: str,
    service_requested: str,
    condition_notes: str,
    mobile_or_shop_preference: str,
    customer_location: str,
    preferred_date: str,
    preferred_time: str,
    urgency: str | None,
    budget_signal: str | None,
    lead_summary: str,
    transcript: list[dict],
    status: str = "new",
    owner_notified: bool = True,
    channel: str = "phone",
):
    lead = new_lead(business_id=BUSINESS_ID, call_sid=f"demo_{customer_name.split()[0].lower()}")
    lead["channel"] = channel
    lead["status"] = status
    lead["customer_name"] = customer_name
    lead["customer_phone"] = customer_phone
    lead["vehicle_year"] = vehicle_year
    lead["vehicle_make"] = vehicle_make
    lead["vehicle_model"] = vehicle_model
    lead["vehicle_color"] = vehicle_color
    lead["service_requested"] = service_requested
    lead["condition_notes"] = condition_notes
    lead["mobile_or_shop_preference"] = mobile_or_shop_preference
    lead["customer_location"] = customer_location
    lead["preferred_date"] = preferred_date
    lead["preferred_time"] = preferred_time
    lead["urgency"] = urgency
    lead["budget_signal"] = budget_signal
    lead["lead_summary"] = lead_summary
    lead["transcript"] = transcript
    lead["owner_notified"] = owner_notified
    lead["owner_notified_at"] = _ts(minutes_ago - 1) if owner_notified else None
    lead["created_at"] = _ts(minutes_ago)
    lead["updated_at"] = _ts(max(0, minutes_ago - 2))
    # Sanity: make sure we used real lead slots only.
    for slot in LEAD_SLOTS:
        lead.setdefault(slot, None)
    return lead


def _turn(role: str, text: str, minutes_ago: int) -> dict:
    return {"role": role, "text": text, "ts": _ts(minutes_ago)}


DEMO_LEADS = [
    _build_lead(
        minutes_ago=12,
        customer_name="Mike Alvarez",
        customer_phone="714-555-1234",
        vehicle_year="2022",
        vehicle_make="Tesla",
        vehicle_model="Model 3",
        vehicle_color="black",
        service_requested="Ceramic Coating",
        condition_notes="Some swirl marks from automatic car washes. May need paint correction first.",
        mobile_or_shop_preference="shop",
        customer_location="Irvine",
        preferred_date="Saturday",
        preferred_time="morning",
        urgency=None,
        budget_signal="open to paint correction if it makes the coating last",
        lead_summary="Black Tesla Model 3 owner interested in ceramic coating; likely needs paint correction first.",
        status="new",
        transcript=[
            _turn("assistant", "Thanks for calling OC Elite Detailing. How can we help with your vehicle today?", 15),
            _turn("user", "Hey, I've got a black Tesla Model 3 and I'm thinking about getting a ceramic coating.", 14),
            _turn("assistant", "Nice — black on a Model 3 is a great candidate for coating. How does the paint look right now, any swirl marks or scratches?", 14),
            _turn("user", "Yeah some swirls from automatic car washes. Should I do something about that first?", 13),
            _turn("assistant", "Usually we recommend paint correction before coating so the coating locks in a clean finish. Want me to grab your info and have the team confirm pricing?", 13),
            _turn("user", "Sure. Mike Alvarez, 714-555-1234. Saturday morning ideally.", 12),
        ],
    ),
    _build_lead(
        minutes_ago=47,
        customer_name="Daniela Cho",
        customer_phone="949-555-7788",
        vehicle_year="2020",
        vehicle_make="BMW",
        vehicle_model="M4",
        vehicle_color="white",
        service_requested="Paint Correction",
        condition_notes="Heavy swirl marks and a few light scratches around the rear quarter panel.",
        mobile_or_shop_preference="shop",
        customer_location="Costa Mesa",
        preferred_date="next Wednesday",
        preferred_time="afternoon",
        urgency=None,
        budget_signal="ok with multi-day if needed",
        lead_summary="White BMW M4 with heavy swirls; wants paint correction quote and possible coating after.",
        status="contacted",
        transcript=[
            _turn("assistant", "Thanks for calling OC Elite Detailing. How can we help with your vehicle today?", 50),
            _turn("user", "I have a white BMW M4 with a bunch of swirl marks. What do you charge for paint correction?", 49),
            _turn("assistant", "Paint correction usually runs $400–$1,200 depending on paint condition and vehicle size. We confirm the exact quote after seeing the car. Want to bring it in?", 48),
            _turn("user", "Yeah, next Wednesday afternoon if you have something.", 47),
        ],
    ),
    _build_lead(
        minutes_ago=110,
        customer_name="Aaron Walker",
        customer_phone="657-555-3320",
        vehicle_year="2018",
        vehicle_make="Toyota",
        vehicle_model="Camry",
        vehicle_color="silver",
        service_requested="Full Detail",
        condition_notes="Family car, pet hair in the back seats, normal exterior wear.",
        mobile_or_shop_preference="shop",
        customer_location="Santa Ana",
        preferred_date="Friday",
        preferred_time="10:00 am",
        urgency=None,
        budget_signal="cost-conscious",
        lead_summary="Silver Camry needs a full detail with pet hair removal in back seats. Wants Friday morning.",
        status="booked",
        transcript=[
            _turn("assistant", "Thanks for calling OC Elite Detailing. How can we help with your vehicle today?", 115),
            _turn("user", "Hi, looking to get my 2018 Camry detailed. It's the family car so it's pretty rough inside.", 114),
            _turn("assistant", "We can definitely help. Our full detail is $180–$350 depending on condition. Any pet hair or anything to flag?", 113),
            _turn("user", "Yeah a lot of pet hair in the back. Can you do Friday morning at 10?", 112),
            _turn("assistant", "Friday 10 am works. What's the best phone number to put on the appointment?", 111),
            _turn("user", "Aaron Walker, 657-555-3320.", 110),
        ],
    ),
    _build_lead(
        minutes_ago=200,
        customer_name="Jess Patel",
        customer_phone="714-555-9011",
        vehicle_year="2021",
        vehicle_make="Ford",
        vehicle_model="F-150",
        vehicle_color="blue",
        service_requested="Interior Detail",
        condition_notes="Work truck — lots of mud and dust, vinyl seats. No leather.",
        mobile_or_shop_preference="mobile",
        customer_location="Anaheim",
        preferred_date=None,
        preferred_time=None,
        urgency="soon",
        budget_signal=None,
        lead_summary="Blue F-150 work truck — wants mobile interior detail in Anaheim, ASAP this week.",
        status="new",
        transcript=[
            _turn("assistant", "Thanks for reaching out to OC Elite Detailing! What vehicle are we helping you with today?", 205),
            _turn("user", "I have a 2021 F-150 work truck. Interior is destroyed. Can you come to me in Anaheim?", 204),
            _turn("assistant", "Yep, Anaheim is in our mobile service area. Interior details on trucks usually run $150–$220 depending on condition. When were you hoping for?", 203),
            _turn("user", "Sometime this week, sooner the better. Jess Patel, 714-555-9011.", 200),
        ],
    ),
    _build_lead(
        minutes_ago=320,
        customer_name="Sara Nguyen",
        customer_phone="949-555-4422",
        vehicle_year="2019",
        vehicle_make="Mercedes",
        vehicle_model="C-Class",
        vehicle_color="grey",
        service_requested="Full Detail",
        condition_notes="Leather interior, garage kept, just wants a refresh before selling it.",
        mobile_or_shop_preference="mobile",
        customer_location="Newport Beach",
        preferred_date="Sunday",
        preferred_time="afternoon",
        urgency=None,
        budget_signal="willing to pay for a premium job",
        lead_summary="Grey Mercedes C-Class — wants mobile full detail in Newport before listing for sale.",
        status="new",
        channel="chat",
        transcript=[
            _turn("assistant", "Hi — what vehicle are we helping you with today?", 325),
            _turn("user", "Mercedes C-Class, 2019. I'm putting it up for sale and want it looking sharp. Do you come to Newport?", 324),
            _turn("assistant", "Yes, Newport Beach is in our mobile service area. A full detail typically runs $180–$350 depending on size and condition. Want to set a time?", 323),
            _turn("user", "Sunday afternoon would be perfect. Sara Nguyen, 949-555-4422.", 320),
        ],
    ),
]


def main() -> None:
    replace = "--replace" in sys.argv
    if replace and LEADS_LOG_PATH.exists():
        LEADS_LOG_PATH.unlink()
        print(f"Removed existing {LEADS_LOG_PATH}")

    for lead in DEMO_LEADS:
        save_lead(lead)
        print(f"Saved demo lead: {lead['customer_name']} ({lead['service_requested']})")

    print(f"\nWrote {len(DEMO_LEADS)} demo leads to {LEADS_LOG_PATH}")
    print("Open the dashboard at http://localhost:3002/inbox to see them.")


if __name__ == "__main__":
    main()
