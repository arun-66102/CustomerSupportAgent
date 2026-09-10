"""
LLM-based intent classifier using Groq (llama-3.3-70b-versatile).
Returns structured JSON with intent label and confidence score.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

from src.intent.taxonomy import INTENT_LABELS, get_intent_risk, get_taxonomy_prompt_section

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

_groq_client = None


def _get_client():
    global _groq_client
    api_key = os.getenv("GROQ_API_KEY", "")
    if _groq_client is None and GROQ_AVAILABLE and api_key:
        _groq_client = Groq(api_key=api_key)
    return _groq_client


SYSTEM_PROMPT = """You are an expert customer support intent classifier for Apple Support.
Your task is to classify the customer's message into exactly one intent from the provided list.
You must respond ONLY with a valid JSON object — no prose, no markdown, no explanation.

{taxonomy}

Respond with this exact JSON format:
{{
  "intent": "<one of the intent names above>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence explaining why>"
}}
"""


def classify_intent_llm(customer_message: str) -> dict:
    """
    Classify intent using Groq LLM.
    Returns: {"intent": str, "confidence": float, "reasoning": str, "method": "llm"}
    Falls back to keyword-based classification if Groq is unavailable.
    """
    client = _get_client()

    if client is None:
        return classify_intent_keyword(customer_message)

    taxonomy_section = get_taxonomy_prompt_section()
    system = SYSTEM_PROMPT.format(taxonomy=taxonomy_section)
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Customer message: {customer_message}"}
            ],
            temperature=0.1,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()

        # Extract JSON even if LLM adds text or markdown around it
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                intent = result.get("intent", "general_question")
                if intent not in INTENT_LABELS:
                    intent = "general_question"
                return {
                    "intent": intent,
                    "confidence": float(result.get("confidence", 0.85)),
                    "reasoning": result.get("reasoning", ""),
                    "risk": get_intent_risk(intent),
                    "method": "llm"
                }
            except json.JSONDecodeError:
                pass

        # Regex fallback for intent extraction if JSON is cut off
        intent_match = re.search(r'"intent"\s*:\s*"([^"]+)"', raw)
        if intent_match:
            intent = intent_match.group(1)
            if intent in INTENT_LABELS:
                conf_match = re.search(r'"confidence"\s*:\s*([0-9\.]+)', raw)
                conf = float(conf_match.group(1)) if conf_match else 0.80
                return {
                    "intent": intent,
                    "confidence": conf,
                    "reasoning": "Extracted from LLM response",
                    "risk": get_intent_risk(intent),
                    "method": "llm"
                }
    except Exception as e:
        print(f"[Classifier] LLM error: {e}, falling back to keyword classifier")

    return classify_intent_keyword(customer_message)


def classify_intent_keyword(customer_message: str) -> dict:
    """
    Fallback keyword-based intent classifier.
    Uses word overlap with intent keywords.
    """
    from src.intent.taxonomy import INTENT_TAXONOMY

    message_lower = customer_message.lower()
    scores = {}

    for intent, info in INTENT_TAXONOMY.items():
        score = sum(1 for kw in info["keywords"] if kw in message_lower)
        scores[intent] = score

    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]
    total = sum(scores.values()) or 1

    if best_score == 0:
        best_intent = "general_question"
        confidence = 0.40
    else:
        confidence = min(0.45 + (best_score / total) * 0.40, 0.85)

    return {
        "intent": best_intent,
        "confidence": round(confidence, 2),
        "reasoning": f"Keyword match: '{best_intent}' scored {best_score} keyword hits.",
        "risk": get_intent_risk(best_intent),
        "method": "keyword"
    }


if __name__ == "__main__":
    tests = [
        "My phone battery drains really fast after the iOS update",
        "Someone hacked my Apple ID and I can't get in",
        "The camera on my iPhone is blurry",
        "How do I enable dark mode on my iPhone?",
        "I was charged for an app I never downloaded",
    ]
    for msg in tests:
        result = classify_intent_llm(msg)
        print(f"\nMessage: {msg}")
        print(f"  Intent: {result['intent']} (conf={result['confidence']:.2f}, risk={result['risk']}, method={result['method']})")
        print(f"  Reason: {result['reasoning']}")
