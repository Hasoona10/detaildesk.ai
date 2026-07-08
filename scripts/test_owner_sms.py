"""One-shot smoke test: send a fake-lead owner SMS through Twilio.

Run with:
    python scripts/test_owner_sms.py

Prints the result dict from sms_notify.notify_owner.
Safe to run repeatedly. Costs ~$0.0075 per text on a US number.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    print("WARNING: python-dotenv not installed; relying on shell env vars.")

from backend.sms_notify import notify_owner


FAKE_LEAD = {
    "id": "smoke-test-001",
    "customer_name": "Test Customer",
    "customer_phone": "555-555-1234",
    "vehicle_year": "2022",
    "vehicle_make": "Tesla",
    "vehicle_model": "Model 3",
    "vehicle_color": "black",
    "service_requested": "Ceramic Coating",
    "condition_notes": "Smoke test from the AI receptionist setup.",
    "mobile_or_shop_preference": "shop",
    "customer_location": "Irvine",
    "preferred_date": "Saturday",
    "preferred_time": "morning",
    "urgency": None,
    "lead_summary": "Smoke test owner-SMS path -- if you see this, Twilio is wired up correctly.",
}


def main() -> int:
    print("Owner SMS smoke test")
    print("=" * 50)
    print(f"OWNER_SMS_NUMBER:    {os.getenv('OWNER_SMS_NUMBER') or '(unset)'}")
    print(f"TWILIO_PHONE_NUMBER: {os.getenv('TWILIO_PHONE_NUMBER') or '(unset)'}")
    print(f"TWILIO_ACCOUNT_SID:  {os.getenv('TWILIO_ACCOUNT_SID') or '(unset)'}")
    api_key = os.getenv("TWILIO_API_KEY_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    print(f"API Key SID set:     {bool(api_key)}")
    print(f"API Key Secret set:  {bool(os.getenv('TWILIO_API_KEY_SECRET'))}")
    print(f"Auth Token set:      {bool(auth_token)}")
    print("=" * 50)
    print()

    result = notify_owner(FAKE_LEAD)
    print("Result:")
    print(json.dumps({k: v for k, v in result.items() if k != "body"}, indent=2))
    print()
    print("Body that would be sent:")
    print("-" * 50)
    print(result["body"])
    print("-" * 50)

    if result.get("sent"):
        print("\nSUCCESS — check your phone.")
        return 0
    print(f"\nNOT SENT — reason: {result.get('reason')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
