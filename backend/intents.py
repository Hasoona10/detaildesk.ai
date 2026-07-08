"""
Intent classification for the auto-detailing AI receptionist.

Fallback strategy stays the same as before:
1. Try ML model first (fast/cheap when trained)
2. Fall back to rule-based keyword matching
3. Final fallback to LLM API
"""
from enum import Enum
from typing import Optional

import os
from .utils.logger import logger

# Lazy initialization - client will be created when needed
_client = None


def get_openai_client():
    """Get or create OpenAI client with API key from environment.

    The `openai` package is imported lazily here so the rest of the codebase
    (intent enum, rule-based classifier, training scripts) can be used in
    environments where the OpenAI SDK isn't installed.
    """
    global _client
    if _client is None:
        from openai import OpenAI  # imported lazily

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Make sure .env file is loaded."
            )
        _client = OpenAI(api_key=api_key)
    return _client


class Intent(str, Enum):
    """Customer intent types for the auto-detailing receptionist."""
    GREETING = "greeting"
    REQUEST_QUOTE = "request_quote"
    ASK_SERVICES = "ask_services"
    ASK_PRICING = "ask_pricing"
    BOOK_APPOINTMENT = "book_appointment"
    ASK_MOBILE_SERVICE = "ask_mobile_service"
    ASK_CERAMIC_COATING = "ask_ceramic_coating"
    ASK_PAINT_CORRECTION = "ask_paint_correction"
    ASK_HOURS = "ask_hours"
    ASK_LOCATION = "ask_location"
    ASK_SERVICE_AREA = "ask_service_area"
    ASK_VEHICLE_SUPPORT = "ask_vehicle_support"
    CALLBACK_REQUEST = "callback_request"
    URGENT_DETAIL_REQUEST = "urgent_detail_request"
    COMPLAINT_OR_ISSUE = "complaint_or_issue"
    GENERAL_QUESTION = "general_question"
    GOODBYE = "goodbye"
    UNKNOWN = "unknown"


# Keyword sets are ordered by specificity: more specific intents are checked
# before more generic ones (e.g. ceramic coating before ask_services).
INTENT_KEYWORDS = {
    Intent.URGENT_DETAIL_REQUEST: [
        "today", "tonight", "asap", "right now", "as soon as possible",
        "tomorrow morning", "tomorrow", "before the weekend", "emergency",
    ],
    Intent.ASK_CERAMIC_COATING: [
        "ceramic", "ceramic coating", "coating", "graphene", "nano coating",
    ],
    Intent.ASK_PAINT_CORRECTION: [
        "paint correction", "swirl", "swirl marks", "polish", "scratch",
        "scratches", "oxidation", "water spots", "buff", "compounding",
    ],
    Intent.ASK_MOBILE_SERVICE: [
        "mobile", "come to me", "come out", "at my house", "at my apartment",
        "do you travel", "you guys travel", "service my area",
    ],
    Intent.ASK_SERVICE_AREA: [
        "service area", "do you service", "do you cover", "areas you cover",
        "irvine", "anaheim", "tustin", "newport", "costa mesa", "huntington",
        "santa ana", "orange county",
    ],
    Intent.ASK_VEHICLE_SUPPORT: [
        "tesla", "ev", "electric", "suv", "truck", "exotic", "porsche",
        "lamborghini", "ferrari", "lifted", "do you detail",
    ],
    Intent.REQUEST_QUOTE: [
        "quote", "estimate", "how much would", "how much for", "what would it cost",
        "what would you charge", "ballpark",
    ],
    Intent.ASK_PRICING: [
        "price", "cost", "how much", "expensive", "cheap", "dollar", "$",
        "pricing",
    ],
    Intent.BOOK_APPOINTMENT: [
        "book", "schedule", "appointment", "available", "availability",
        "any openings", "can i come in", "set up a time", "this saturday",
        "this weekend",
    ],
    Intent.ASK_SERVICES: [
        "services", "what do you do", "do you offer", "do you guys do",
        "interior detail", "exterior detail", "full detail", "maintenance wash",
    ],
    Intent.ASK_HOURS: [
        "hours", "open", "closed", "what time", "when do you", "when are you",
    ],
    Intent.ASK_LOCATION: [
        "where are you", "address", "location", "directions", "find you",
    ],
    Intent.CALLBACK_REQUEST: [
        "call me back", "give me a call", "ring me", "call back later",
    ],
    Intent.COMPLAINT_OR_ISSUE: [
        "complaint", "unhappy", "refund", "issue with", "problem with",
        "messed up", "ruined",
    ],
    Intent.GREETING: [
        "hello", "hi ", "hi,", "hey", "good morning", "good afternoon",
        "good evening", "what's up",
    ],
    Intent.GOODBYE: [
        "bye", "goodbye", "thanks", "thank you", "see you", "later",
        "that's all",
    ],
}


# ---------------- LLM classification ----------------

INTENT_DESCRIPTIONS = """- greeting: Initial greeting or salutation
- request_quote: Customer is asking for a quote or estimate for a specific service
- ask_services: Asking what services we offer
- ask_pricing: Asking about prices or cost
- book_appointment: Customer wants to book or schedule an appointment
- ask_mobile_service: Asking whether we come to the customer
- ask_ceramic_coating: Anything about ceramic coating
- ask_paint_correction: Swirl marks, scratches, oxidation, polish, paint correction
- ask_hours: Business hours
- ask_location: Where we're located
- ask_service_area: Which cities or zip codes we cover
- ask_vehicle_support: Whether we detail a specific vehicle type (EV, exotic, truck, etc.)
- callback_request: Customer wants a callback
- urgent_detail_request: Customer needs detailing very soon
- complaint_or_issue: A complaint or post-service problem
- general_question: Any other general question about the business
- goodbye: Closing or farewell"""


async def classify_intent_llm(text: str) -> Intent:
    """Classify customer intent using LLM as the final fallback."""
    try:
        prompt = f"""Classify the following customer message for an auto detailing receptionist into ONE of these intents:

{INTENT_DESCRIPTIONS}

Message: "{text}"

Respond with ONLY the intent name (lowercase, no punctuation)."""

        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an intent classifier for an auto detailing AI receptionist."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=20,
        )

        intent_str = response.choices[0].message.content.strip().lower()
        try:
            intent = Intent(intent_str)
        except ValueError:
            logger.warning(f"Unknown intent returned: {intent_str}, defaulting to UNKNOWN")
            intent = Intent.UNKNOWN

        logger.info(f"Intent classified as: {intent.value} for text: {text[:50]}...")
        return intent

    except Exception as e:
        logger.error(f"Error classifying intent: {str(e)}")
        return Intent.UNKNOWN


def classify_intent_rule_based(text: str) -> Intent:
    """Simple rule-based intent classification using ordered keyword sets."""
    text_lower = text.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                logger.info(f"Intent classified as: {intent.value} (keyword: {keyword})")
                return intent
    return Intent.GENERAL_QUESTION


# ---------------- ML classification (optional, lazy loaded) ----------------

_ml_classifier = None
_ml_classifier_path: Optional[str] = None


def _load_ml_classifier(model_path: Optional[str] = None):
    """Load the ML classifier if available."""
    global _ml_classifier, _ml_classifier_path

    if model_path is None:
        from pathlib import Path
        try:
            from .ml_models.model_registry import get_registry
            registry = get_registry()
            latest_model = registry.get_latest_model("intent_classifier")
        except Exception:
            latest_model = None

        if latest_model:
            model_path = latest_model['path']
        else:
            model_path = str(Path("./models") / "random_forest_tfidf")

    if _ml_classifier is not None and _ml_classifier_path == model_path:
        return _ml_classifier

    try:
        from pathlib import Path
        from .ml_models.intent_classifier import IntentClassifier
        from .ml_models.feature_extractor import FeatureExtractor

        model_dir = Path(model_path)
        if not model_dir.exists():
            logger.debug(f"ML model not found at {model_path}")
            return None

        extractor_files = list(model_dir.glob("*_extractor.pkl"))
        if not extractor_files:
            logger.debug(f"Feature extractor not found in {model_dir}")
            return None

        feature_extractor = FeatureExtractor.load(extractor_files[0])
        _ml_classifier = IntentClassifier.load(model_dir, feature_extractor)
        _ml_classifier_path = model_path
        logger.info(f"Loaded ML classifier from {model_path}")
        return _ml_classifier

    except Exception as e:
        logger.warning(f"Failed to load ML classifier: {str(e)}")
        return None


def classify_intent_ml(text: str, model_path: Optional[str] = None) -> Intent:
    """Classify intent using a trained ML model."""
    classifier = _load_ml_classifier(model_path)
    if classifier is None:
        raise ValueError("ML classifier not available. Train a model first.")
    try:
        intent = classifier.predict(text)
        logger.info(f"Intent classified as: {intent.value} (ML) for text: {text[:50]}...")
        return intent
    except Exception as e:
        logger.error(f"Error in ML classification: {str(e)}")
        raise


async def classify_intent(
    text: str,
    method: str = "auto",
    use_llm: Optional[bool] = None,
    ml_model_path: Optional[str] = None,
) -> Intent:
    """Classify intent. method ∈ {auto, ml, rule, llm}.

    'auto' is the cost-optimized fallback chain: ML → rule → LLM.
    """
    if use_llm is not None:
        method = "llm" if use_llm else "rule"

    if method == "ml":
        try:
            return classify_intent_ml(text, ml_model_path)
        except Exception as e:
            logger.warning(f"ML classification failed: {str(e)}, falling back to rule-based")
            return classify_intent_rule_based(text)

    if method == "rule":
        return classify_intent_rule_based(text)

    if method == "llm":
        return await classify_intent_llm(text)

    if method == "auto":
        try:
            classifier = _load_ml_classifier(ml_model_path)
            if classifier is not None:
                intent = classifier.predict(text)
                logger.info(f"Intent classified as: {intent.value} (ML) for text: {text[:50]}...")
                return intent
        except Exception as e:
            logger.debug(f"ML classification failed: {str(e)}")

        try:
            intent = classify_intent_rule_based(text)
            if intent != Intent.GENERAL_QUESTION:
                return intent
        except Exception as e:
            logger.debug(f"Rule-based classification failed: {str(e)}")

        return await classify_intent_llm(text)

    raise ValueError(f"Unknown method: {method}. Use 'auto', 'ml', 'rule', or 'llm'")


# Training phrase corpus for the new detailing intents. Used by the
# synthetic data generator / trainer to bootstrap an ML model.
TRAINING_EXAMPLES = {
    Intent.GREETING: [
        "hello", "hi there", "hey, how's it going", "good morning",
        "good afternoon", "hey what's up",
    ],
    Intent.REQUEST_QUOTE: [
        "how much for a full detail?",
        "what do you charge for ceramic coating?",
        "how much to detail a Tesla Model 3?",
        "can I get a quote for my BMW?",
        "what would it cost for interior and exterior?",
        "can you give me an estimate for paint correction?",
        "ballpark price for a maintenance wash?",
    ],
    Intent.ASK_SERVICES: [
        "what services do you offer?",
        "do you do interior and exterior?",
        "what's included in a full detail?",
        "do you guys do detailing on trucks?",
        "tell me what you do",
    ],
    Intent.ASK_PRICING: [
        "how much do you charge?",
        "what are your prices?",
        "is detailing expensive?",
        "what's the cost of an interior detail?",
    ],
    Intent.BOOK_APPOINTMENT: [
        "can I book for Saturday?",
        "do you have anything tomorrow morning?",
        "can I schedule a detail next week?",
        "are you available Friday?",
        "I need my car detailed before the weekend",
        "any openings this week?",
        "what time can I bring my car in?",
    ],
    Intent.ASK_MOBILE_SERVICE: [
        "do you come to me?",
        "are you mobile?",
        "can you detail at my house?",
        "do you service Irvine?",
        "can you come to my apartment?",
        "do you guys travel out to Newport?",
    ],
    Intent.ASK_CERAMIC_COATING: [
        "do you guys do ceramic coating?",
        "how much is ceramic coating?",
        "is ceramic coating worth it?",
        "does ceramic coating prevent scratches?",
        "how long does a coating take?",
        "what's the difference between coating and wax?",
    ],
    Intent.ASK_PAINT_CORRECTION: [
        "can you remove swirl marks?",
        "my black car has scratches",
        "do you do paint correction?",
        "can you fix oxidation?",
        "can you polish my car?",
        "I've got a lot of water spots, can you fix that?",
    ],
    Intent.ASK_HOURS: [
        "what are your hours?",
        "are you open today?",
        "when do you close?",
        "what time do you open on Saturday?",
    ],
    Intent.ASK_LOCATION: [
        "where are you located?",
        "what's your address?",
        "how do I find your shop?",
    ],
    Intent.ASK_SERVICE_AREA: [
        "do you service Costa Mesa?",
        "what areas do you cover?",
        "do you come to Anaheim?",
    ],
    Intent.ASK_VEHICLE_SUPPORT: [
        "do you detail Teslas?",
        "do you work on lifted trucks?",
        "can you detail an exotic?",
        "do you do EVs?",
    ],
    Intent.CALLBACK_REQUEST: [
        "can you call me back?",
        "give me a call later",
        "I'd like a callback",
    ],
    Intent.URGENT_DETAIL_REQUEST: [
        "I need it detailed today",
        "any chance you can come out tonight?",
        "I need this done before tomorrow",
    ],
    Intent.COMPLAINT_OR_ISSUE: [
        "there's a swirl mark you missed",
        "I'm not happy with the result",
        "can I get a refund?",
    ],
    Intent.GENERAL_QUESTION: [
        "do you accept credit cards?",
        "do you sell gift cards?",
        "do you have a referral program?",
    ],
    Intent.GOODBYE: [
        "thanks, that's all",
        "bye",
        "goodbye, see you",
        "thank you, have a good one",
    ],
}
