"""
Owner SMS notifications via Twilio.

Sends a concise lead summary to the business owner when the AI captures
a qualified detailing lead. Falls back to a no-op (logged warning) when
Twilio credentials or the owner number aren't configured, so the rest
of the demo keeps working.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from .lead_value import (
    estimate_value,
    format_value,
    lead_temperature,
    recommended_next_step,
)
from .utils.logger import logger

SMS_SEND_RETRIES = 2  # total attempts = 1 + retries
SMS_RETRY_DELAY_S = 2.0


def _format_vehicle(lead: Dict[str, Any]) -> str:
    parts = [
        lead.get("vehicle_color"),
        lead.get("vehicle_year"),
        lead.get("vehicle_make"),
        lead.get("vehicle_model"),
    ]
    parts = [str(p).strip() for p in parts if p]
    return " ".join(p.title() if p.islower() else p for p in parts) if parts else "Not provided"


def _format_preferred_time(lead: Dict[str, Any]) -> str:
    date = lead.get("preferred_date")
    time_ = lead.get("preferred_time")
    if date and time_:
        return f"{date} {time_}"
    return date or time_ or ""


def build_owner_summary(
    lead: Dict[str, Any],
    business_data: Optional[Dict[str, Any]] = None,
) -> str:
    """The "money feature": a clean, scannable lead summary SMS.

    Format:
        [phone emoji] New detailing lead

        Mike Rodriguez
        714-928-4731

        Vehicle: Black Tesla Model 3
        Service: Ceramic Coating
        Condition: Swirl marks visible in sun
        Timeline: This weekend
        Value: $800-$1,500
        Status: Warm lead

        Next step:
        Call back today and offer inspection slot.
    """
    temp = lead_temperature(lead, business_data)
    header = "\U0001F525 Hot detailing lead" if temp == "hot" else "\U0001F4DE New detailing lead"

    lines = [header, ""]
    lines.append(lead.get("customer_name") or "Unknown caller")
    if lead.get("customer_phone"):
        lines.append(lead["customer_phone"])
    lines.append("")

    vehicle = _format_vehicle(lead)
    if vehicle != "Not provided":
        lines.append(f"Vehicle: {vehicle}")
    if lead.get("service_requested"):
        lines.append(f"Service: {lead['service_requested']}")
    if lead.get("condition_notes"):
        lines.append(f"Condition: {lead['condition_notes']}")
    timeline = _format_preferred_time(lead)
    if timeline:
        lines.append(f"Timeline: {timeline}")
    if lead.get("customer_location"):
        pref = lead.get("mobile_or_shop_preference")
        lines.append(
            f"Location: {lead['customer_location']}" + (f" ({pref})" if pref else "")
        )
    value = format_value(estimate_value(lead, business_data))
    if value:
        lines.append(f"Value: {value}")
    lines.append(f"Status: {temp.capitalize()} lead")

    lines.append("")
    lines.append("Next step:")
    lines.append(recommended_next_step(lead, business_data))

    return "\n".join(lines)


def _resolve_owner_number(business_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Owner SMS number resolution: env wins, then business_data, then None."""
    env_num = os.getenv("OWNER_SMS_NUMBER")
    if env_num:
        return env_num
    if business_data:
        owner = business_data.get("owner_notification") or {}
        num = owner.get("owner_sms_number")
        if num:
            return num
    return None


def notify_owner(
    lead: Dict[str, Any],
    business_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Send the owner an SMS summary for a qualified lead.

    Returns a dict describing what happened: {sent: bool, reason: str, body: str}.
    Never raises — SMS failure should not break a phone call.
    """
    body = build_owner_summary(lead, business_data)
    result: Dict[str, Any] = {"sent": False, "reason": "", "body": body}

    sms_enabled = True
    if business_data:
        sms_enabled = (business_data.get("owner_notification") or {}).get("sms_enabled", True)
    if not sms_enabled:
        result["reason"] = "owner_notification.sms_enabled is false"
        logger.info("Owner SMS skipped: notifications disabled in business data")
        return result

    to_number = _resolve_owner_number(business_data)
    if not to_number:
        result["reason"] = "no owner SMS number configured"
        logger.warning("Owner SMS skipped: OWNER_SMS_NUMBER not set and no owner_sms_number in business data")
        return result

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    api_key_sid = os.getenv("TWILIO_API_KEY_SID")
    api_key_secret = os.getenv("TWILIO_API_KEY_SECRET")
    from_number = os.getenv("TWILIO_PHONE_NUMBER") or os.getenv("TWILIO_SMS_FROM")

    have_api_key = bool(api_key_sid and api_key_secret and account_sid)
    have_auth_token = bool(account_sid and auth_token)

    if not from_number or not (have_api_key or have_auth_token):
        result["reason"] = "Twilio credentials not configured"
        logger.warning(
            "Owner SMS skipped: need TWILIO_PHONE_NUMBER + either "
            "(TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET + TWILIO_ACCOUNT_SID) "
            "or (TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN)"
        )
        return result

    from twilio.rest import Client  # imported lazily so missing creds don't break boot

    if have_api_key:
        client = Client(api_key_sid, api_key_secret, account_sid)
    else:
        client = Client(account_sid, auth_token)

    # Retry transient failures — the owner SMS is the money feature.
    last_error: Optional[Exception] = None
    for attempt in range(1 + SMS_SEND_RETRIES):
        try:
            message = client.messages.create(
                body=body,
                from_=from_number,
                to=to_number,
            )
            result["sent"] = True
            result["reason"] = "ok"
            result["sid"] = message.sid
            logger.info(f"Owner SMS sent for lead {lead.get('id')} (sid={message.sid})")
            return result
        except Exception as e:
            last_error = e
            logger.error(f"Owner SMS attempt {attempt + 1} failed: {e}")
            if attempt < SMS_SEND_RETRIES:
                time.sleep(SMS_RETRY_DELAY_S)

    result["reason"] = f"twilio error: {last_error}"
    return result
