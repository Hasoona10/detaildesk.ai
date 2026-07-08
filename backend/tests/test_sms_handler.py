"""Tests for the Twilio inbound SMS handler.

We don't talk to Twilio or the LLM here — `process_customer_message` is
monkey-patched to a deterministic stub so we can verify the SMS routing,
STOP/HELP compliance, and that the right session id is used.
"""
from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from backend import twilio_sms_handler


def _make_request(form: Dict[str, str]):
    """Tiny stand-in for FastAPI's Request for the .form() coroutine."""

    class _Form(dict):
        def get(self, key, default=None):  # noqa: D401 - mimic Form interface
            return super().get(key, default)

    async def _form():
        return _Form(form)

    return SimpleNamespace(form=_form)


def _twiml_message_body(response_obj) -> str:
    """Pull the <Message> body out of a TwiML response."""
    text = response_obj.body.decode("utf-8") if isinstance(response_obj.body, bytes) else response_obj.body
    root = ET.fromstring(text)
    message = root.find("Message")
    assert message is not None, f"No <Message> in TwiML: {text!r}"
    return (message.text or "").strip()


def test_sms_session_id_is_stable_per_phone():
    a = twilio_sms_handler._sms_session_id("+17145551234")
    b = twilio_sms_handler._sms_session_id("+17145551234")
    c = twilio_sms_handler._sms_session_id("+17145559999")
    assert a == b
    assert a != c
    assert a.startswith("sms_")


def test_stop_keyword_returns_unsubscribe_without_calling_engine(monkeypatch):
    called = {"engine": 0}

    async def _spy(**kwargs):
        called["engine"] += 1
        return "should not be called"

    monkeypatch.setattr(twilio_sms_handler, "process_customer_message", _spy)

    request = _make_request({"From": "+17145551234", "Body": "STOP", "MessageSid": "SM1"})
    response = asyncio.run(twilio_sms_handler.handle_incoming_sms(request))

    body = _twiml_message_body(response)
    assert "unsubscribed" in body.lower()
    assert called["engine"] == 0, "STOP must short-circuit without calling the LLM"


def test_help_keyword_returns_business_info_without_calling_engine(monkeypatch):
    called = {"engine": 0}

    async def _spy(**kwargs):
        called["engine"] += 1
        return "should not be called"

    monkeypatch.setattr(twilio_sms_handler, "process_customer_message", _spy)

    request = _make_request({"From": "+17145551234", "Body": "HELP", "MessageSid": "SM2"})
    response = asyncio.run(twilio_sms_handler.handle_incoming_sms(request))

    body = _twiml_message_body(response)
    assert "stop" in body.lower(), "HELP reply should mention how to opt out"
    assert called["engine"] == 0


def test_regular_sms_routes_to_conversation_engine(monkeypatch):
    captured: Dict[str, Any] = {}

    async def _stub(**kwargs):
        captured.update(kwargs)
        return "Hey, thanks for texting OC Elite Detailing!"

    monkeypatch.setattr(twilio_sms_handler, "process_customer_message", _stub)

    request = _make_request(
        {
            "From": "+17145551234",
            "Body": "Do you guys do ceramic coating?",
            "MessageSid": "SM3",
        }
    )
    response = asyncio.run(twilio_sms_handler.handle_incoming_sms(request))
    body = _twiml_message_body(response)

    assert "OC Elite Detailing" in body
    assert captured["text"] == "Do you guys do ceramic coating?"
    assert captured["call_sid"] == "sms_+17145551234"
    assert captured["business_id"]  # whatever business_data resolves to


def test_missing_body_returns_friendly_prompt(monkeypatch):
    async def _should_not_be_called(**kwargs):  # pragma: no cover - safety net
        raise AssertionError("engine should not be called when Body is missing")

    monkeypatch.setattr(twilio_sms_handler, "process_customer_message", _should_not_be_called)

    request = _make_request({"From": "+17145551234", "Body": "", "MessageSid": "SM4"})
    response = asyncio.run(twilio_sms_handler.handle_incoming_sms(request))
    body = _twiml_message_body(response)
    assert "resend" in body.lower() or "didn't catch" in body.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
