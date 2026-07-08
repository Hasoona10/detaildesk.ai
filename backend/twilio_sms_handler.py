"""
Twilio inbound SMS webhook for the AI detailing receptionist.

A customer texts the shop's Twilio number; this module:

1. Extracts the sender's phone (`From`) and message body (`Body`).
2. Handles SMS compliance keywords (STOP/HELP) deterministically — no LLM needed.
3. Reuses `backend.call_flow.process_customer_message` so the AI behaves
   identically across phone, web chat, and SMS. The session id is derived
   from the sender's phone, so multi-turn conversations resume automatically
   whenever the same number texts again.
4. Replies via TwiML <Message>, which Twilio sends back to the customer.

Twilio console setup (once deployed):
  Phone Numbers → your number → Messaging → "A MESSAGE COMES IN" → webhook
  → POST https://<your-domain>/api/twilio/sms/incoming
"""
from __future__ import annotations

from fastapi import Request, Response
from twilio.twiml.messaging_response import MessagingResponse

from .call_flow import BUSINESS_DATA, process_customer_message
from .utils.logger import logger


# Twilio's recommended opt-out / help keywords. We respond to these
# without calling the LLM so STOP always works instantly.
STOP_KEYWORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit", "stop all"}
HELP_KEYWORDS = {"help", "info"}

# Max SMS body chars before Twilio segments. We let Twilio segment — this is
# just used to log a warning when the AI's reply is long enough to fragment.
SMS_SOFT_LIMIT = 320


def _sms_session_id(from_number: str) -> str:
    """Stable session id per sender so multi-turn conversations resume.

    We don't use Twilio's MessageSid because that changes per inbound text;
    using the sender's phone keeps the conversation state across messages.
    """
    return f"sms_{from_number}"


def _stop_reply(business_name: str) -> str:
    return (
        f"You're unsubscribed from {business_name} messages. No more texts will be sent. "
        "Reply START to resubscribe."
    )


def _help_reply(business_name: str, phone: str | None) -> str:
    base = (
        f"{business_name} AI receptionist. "
        "Text us about detailing, ceramic coating, paint correction, or to book."
    )
    if phone:
        base += f" Reach a human at {phone}. Reply STOP to opt out."
    else:
        base += " Reply STOP to opt out."
    return base


def _twiml(reply_text: str) -> Response:
    resp = MessagingResponse()
    resp.message(reply_text)
    return Response(content=str(resp), media_type="application/xml")


async def handle_incoming_sms(request: Request) -> Response:
    """Handle an inbound Twilio SMS webhook (`POST /api/twilio/sms/incoming`).

    Returns TwiML so Twilio sends the reply directly back to the customer.
    """
    try:
        form = await request.form()
    except Exception as e:
        logger.error(f"twilio_sms: failed to parse form data: {e}")
        return _twiml("Sorry, something went wrong. Please call us instead.")

    from_number = (form.get("From") or "").strip()
    body = (form.get("Body") or "").strip()
    message_sid = form.get("MessageSid") or ""

    business_name = BUSINESS_DATA.get("business_name", "the shop")
    contact = BUSINESS_DATA.get("contact") or {}
    business_phone = contact.get("phone")
    business_id = BUSINESS_DATA.get("business_id", "oc_elite_detailing")

    if not from_number or not body:
        logger.warning(f"twilio_sms: missing From or Body (sid={message_sid})")
        return _twiml(
            f"Thanks for texting {business_name}! Could you resend your message? "
            "We didn't catch that one."
        )

    logger.info(f"twilio_sms inbound: sid={message_sid} from={from_number} body={body!r}")

    # SMS compliance: STOP/HELP get deterministic replies, no LLM.
    body_normalised = body.lower().strip(".!? ")
    if body_normalised in STOP_KEYWORDS:
        logger.info(f"twilio_sms: STOP from {from_number}")
        return _twiml(_stop_reply(business_name))
    if body_normalised in HELP_KEYWORDS:
        logger.info(f"twilio_sms: HELP from {from_number}")
        return _twiml(_help_reply(business_name, business_phone))

    # Reuse the same conversation engine the phone + chat widget use.
    # Session id keyed by phone so multi-turn texts resume the same lead.
    session_id = _sms_session_id(from_number)
    try:
        reply = await process_customer_message(
            text=body,
            call_sid=session_id,
            business_id=business_id,
        )
    except Exception as e:
        logger.error(f"twilio_sms: process_customer_message crashed: {e}")
        reply = (
            f"Sorry, something went wrong on our end. Please try again, "
            f"or call us at {business_phone}." if business_phone else
            "Sorry, something went wrong on our end. Please try again in a moment."
        )

    if len(reply) > SMS_SOFT_LIMIT:
        logger.info(
            f"twilio_sms: reply length {len(reply)} > {SMS_SOFT_LIMIT} — Twilio will segment"
        )

    return _twiml(reply)
