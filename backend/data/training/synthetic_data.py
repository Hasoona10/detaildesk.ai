"""Generate synthetic training data for auto-detailing intent classification.

We don't have real call data yet, so we bootstrap a labelled training set by
generating natural-language variations of common detailing phrases for each
intent in `backend.intents.Intent`.
"""
from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Dict, List, Tuple

from backend.intents import Intent


# Seed phrases per intent. Kept short and varied; the generator adds polite/casual
# wrappers around them to create more examples.
INTENT_TEMPLATES: Dict[Intent, List[str]] = {
    Intent.GREETING: [
        "hello",
        "hi there",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "hey, how's it going",
        "what's up",
        "hi I have a quick question",
    ],
    Intent.REQUEST_QUOTE: [
        "how much for a full detail",
        "what do you charge for ceramic coating",
        "how much to detail a Tesla Model 3",
        "can I get a quote for my BMW",
        "what would it cost for interior and exterior",
        "can you give me an estimate for paint correction",
        "ballpark price for a maintenance wash",
        "what's a quote for a full detail on an SUV",
        "rough cost for ceramic coating on a sedan",
    ],
    Intent.ASK_SERVICES: [
        "what services do you offer",
        "what do you guys do",
        "do you do interior and exterior",
        "what's included in a full detail",
        "do you do detailing on trucks",
        "tell me what packages you have",
        "what kind of detailing do you offer",
        "do you offer engine bay cleaning",
    ],
    Intent.ASK_PRICING: [
        "how much do you charge",
        "what are your prices",
        "is detailing expensive",
        "what's the cost of an interior detail",
        "how much for a maintenance wash",
        "what's your price range",
        "how much is just an exterior detail",
    ],
    Intent.BOOK_APPOINTMENT: [
        "can I book for Saturday",
        "do you have anything tomorrow morning",
        "can I schedule a detail next week",
        "are you available Friday",
        "I need my car detailed before the weekend",
        "any openings this week",
        "what time can I bring my car in",
        "can I set up an appointment",
        "do you have a slot Sunday",
    ],
    Intent.ASK_MOBILE_SERVICE: [
        "do you come to me",
        "are you mobile",
        "can you detail at my house",
        "do you service Irvine",
        "can you come to my apartment",
        "do you guys travel out to Newport",
        "I'd want you to come to my place",
        "do you do mobile detailing",
    ],
    Intent.ASK_CERAMIC_COATING: [
        "do you guys do ceramic coating",
        "how much is ceramic coating",
        "is ceramic coating worth it",
        "does ceramic coating prevent scratches",
        "how long does a ceramic coating take",
        "what's the difference between coating and wax",
        "do you offer graphene coatings",
        "I'm thinking about a ceramic coating",
    ],
    Intent.ASK_PAINT_CORRECTION: [
        "can you remove swirl marks",
        "my black car has scratches",
        "do you do paint correction",
        "can you fix oxidation",
        "can you polish my car",
        "I've got a lot of water spots, can you fix that",
        "can you buff out scratches",
        "I want to take the swirls out before coating",
    ],
    Intent.ASK_HOURS: [
        "what are your hours",
        "are you open today",
        "when do you close",
        "what time do you open on Saturday",
        "are you open on Sundays",
        "what time do you close on Friday",
    ],
    Intent.ASK_LOCATION: [
        "where are you located",
        "what's your address",
        "how do I find your shop",
        "what part of town are you in",
        "can you give me directions",
    ],
    Intent.ASK_SERVICE_AREA: [
        "do you service Costa Mesa",
        "what areas do you cover",
        "do you come to Anaheim",
        "do you service Newport Beach",
        "do you go out to Huntington Beach",
        "what cities do you cover",
    ],
    Intent.ASK_VEHICLE_SUPPORT: [
        "do you detail Teslas",
        "do you work on lifted trucks",
        "can you detail an exotic",
        "do you do EVs",
        "do you work on Porsches",
        "can you detail a minivan",
    ],
    Intent.CALLBACK_REQUEST: [
        "can you call me back",
        "give me a call later",
        "I'd like a callback",
        "can someone ring me back",
        "have somebody call me",
    ],
    Intent.URGENT_DETAIL_REQUEST: [
        "I need it detailed today",
        "any chance you can come out tonight",
        "I need this done before tomorrow",
        "I need a detail ASAP",
        "can you fit me in today",
    ],
    Intent.COMPLAINT_OR_ISSUE: [
        "there's a swirl mark you missed",
        "I'm not happy with the result",
        "can I get a refund",
        "the interior still smells",
        "there's a scratch that wasn't there before",
    ],
    Intent.GENERAL_QUESTION: [
        "do you accept credit cards",
        "do you sell gift cards",
        "do you have a referral program",
        "do you offer subscriptions",
        "is there a warranty on the coating",
    ],
    Intent.GOODBYE: [
        "thanks, that's all",
        "bye",
        "goodbye, see you",
        "thank you, have a good one",
        "appreciate it, talk later",
    ],
}


WRAPPERS = [
    "{phrase}",
    "{phrase}?",
    "{phrase} please",
    "Hey, {phrase}",
    "Hi, {phrase}",
    "Quick question — {phrase}",
    "I was wondering, {phrase}",
    "Can you tell me {phrase}",
    "Just calling to ask, {phrase}",
    "{phrase}, by the way",
]


def generate_synthetic_examples(intent: Intent, num_examples: int = 40) -> List[str]:
    """Return a list of `num_examples` natural-language variations for an intent."""
    templates = INTENT_TEMPLATES.get(intent, [])
    if not templates:
        return []

    examples: List[str] = list(templates)
    while len(examples) < num_examples:
        phrase = random.choice(templates)
        wrapper = random.choice(WRAPPERS)
        examples.append(wrapper.format(phrase=phrase))
    return examples[:num_examples]


def create_training_dataset(
    output_path: Path,
    examples_per_intent: int = 60,
    train_split: float = 0.8,
    seed: int = 42,
) -> Tuple[Path, Path]:
    """Build train/test CSVs in the same directory as `output_path`.

    Returns the (train_path, test_path) pair.
    """
    random.seed(seed)

    all_rows: List[Dict[str, str]] = []
    for intent in Intent:
        if intent == Intent.UNKNOWN:
            continue
        for example in generate_synthetic_examples(intent, examples_per_intent):
            all_rows.append({"text": example, "intent": intent.value})

    random.shuffle(all_rows)
    split_idx = int(len(all_rows) * train_split)
    train_rows = all_rows[:split_idx]
    test_rows = all_rows[split_idx:]

    train_path = output_path.parent / "intent_dataset_train.csv"
    test_path = output_path.parent / "intent_dataset_test.csv"

    for path, rows in ((train_path, train_rows), (test_path, test_rows)):
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["text", "intent"])
            writer.writeheader()
            writer.writerows(rows)

    print(f"Wrote {len(train_rows)} train rows to {train_path}")
    print(f"Wrote {len(test_rows)} test rows to {test_path}")
    return train_path, test_path


if __name__ == "__main__":
    output_dir = Path(__file__).parent
    create_training_dataset(
        output_dir / "intent_dataset.csv",
        examples_per_intent=60,
        train_split=0.8,
    )
