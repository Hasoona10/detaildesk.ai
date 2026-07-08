"""Look up the delivery status of one or more Twilio messages by SID.

Usage:
    python scripts/check_sms_status.py SMf2ca73bc89a5065b8950c6ce9cc52114
    python scripts/check_sms_status.py            # lists the 5 most recent messages
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from twilio.rest import Client


def make_client() -> Client:
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    api_key_sid = os.getenv("TWILIO_API_KEY_SID")
    api_key_secret = os.getenv("TWILIO_API_KEY_SECRET")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if api_key_sid and api_key_secret:
        return Client(api_key_sid, api_key_secret, account_sid)
    return Client(account_sid, auth_token)


def print_msg(m) -> None:
    print(f"SID:           {m.sid}")
    print(f"  From:        {m.from_}")
    print(f"  To:          {m.to}")
    print(f"  Status:      {m.status}")
    print(f"  Direction:   {m.direction}")
    print(f"  Date sent:   {m.date_sent}")
    print(f"  Error code:  {m.error_code}")
    print(f"  Error msg:   {m.error_message}")
    print(f"  Body:        {(m.body or '')[:80]!r}")
    print()


def main() -> int:
    client = make_client()
    if len(sys.argv) > 1:
        for sid in sys.argv[1:]:
            print_msg(client.messages(sid).fetch())
    else:
        print("5 most recent messages on this account:\n")
        for m in client.messages.list(limit=5):
            print_msg(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
