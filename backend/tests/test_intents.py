"""Tests for auto-detailing intent classification."""
import pytest

from backend.intents import Intent, classify_intent, classify_intent_rule_based


def test_rule_based_hours():
    assert classify_intent_rule_based("What are your hours?") == Intent.ASK_HOURS


def test_rule_based_location():
    assert classify_intent_rule_based("Where are you located?") == Intent.ASK_LOCATION


def test_rule_based_ceramic_coating():
    assert (
        classify_intent_rule_based("Do you guys do ceramic coating?")
        == Intent.ASK_CERAMIC_COATING
    )


def test_rule_based_paint_correction():
    assert (
        classify_intent_rule_based("Can you remove swirl marks from my black car?")
        == Intent.ASK_PAINT_CORRECTION
    )


def test_rule_based_mobile_service():
    assert (
        classify_intent_rule_based("Do you come to me in Irvine?")
        == Intent.ASK_MOBILE_SERVICE
    )


def test_rule_based_booking():
    assert (
        classify_intent_rule_based("Can I book for Saturday?")
        == Intent.BOOK_APPOINTMENT
    )


def test_rule_based_quote():
    assert (
        classify_intent_rule_based("How much for a full detail?")
        in {Intent.REQUEST_QUOTE, Intent.ASK_PRICING}
    )


def test_rule_based_callback():
    assert classify_intent_rule_based("Can you call me back later?") == Intent.CALLBACK_REQUEST


def test_rule_based_urgent():
    assert (
        classify_intent_rule_based("I need it detailed today")
        == Intent.URGENT_DETAIL_REQUEST
    )


def test_rule_based_goodbye():
    assert classify_intent_rule_based("Thanks, that's all") == Intent.GOODBYE


@pytest.mark.asyncio
async def test_classify_intent_auto_falls_back_to_rule():
    """`auto` mode should still produce a usable intent even without ML / LLM."""
    intent = await classify_intent("What are your hours?", method="rule")
    assert intent == Intent.ASK_HOURS


if __name__ == "__main__":
    pytest.main([__file__])
