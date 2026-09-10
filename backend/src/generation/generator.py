"""
LLM Response Generator using Groq (llama-3.3-70b-versatile).
Generates grounded responses using retrieved historical Apple Support conversations.
Returns structured output with the reply and evidence citations.
"""

import os
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

from src.intent.taxonomy import get_intent_description, get_intent_risk

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


SYSTEM_PROMPT = """You are an Apple Support customer service agent with access to historical support conversations.
Your role is to provide helpful, empathetic, and accurate support responses.

GUIDELINES:
- Be professional, warm, and concise.
- Ground your response in the provided historical evidence — reflect how Apple Support has actually handled similar issues.
- Do NOT make up specific technical steps not supported by the evidence.
- If you're unsure, offer to guide the customer to direct support channels.
- Keep responses under 150 words.
- Always end with an offer to help further.

You must respond ONLY with a valid JSON object in this exact format:
{
  "reply": "<your support response>",
  "evidence_used": [<list of conversation_ids you referenced>],
  "confidence_note": "<one sentence on how well the evidence supported this response>"
}"""


def _build_evidence_context(retrieval_results: list[dict]) -> str:
    """Format retrieved conversations as evidence for the LLM prompt."""
    if not retrieval_results:
        return "No historical evidence available."
    lines = ["Historical Apple Support conversations (most similar first):"]
    for i, r in enumerate(retrieval_results, 1):
        lines.append(f"\n--- Example {i} (ID: {r['conversation_id']}, similarity: {r['similarity']:.2f}) ---")
        lines.append(f"Customer: {r['customer_message']}")
        lines.append(f"Apple Support: {r['brand_response']}")
    return "\n".join(lines)


def generate_response(
    customer_message: str,
    intent: str,
    intent_confidence: float,
    retrieval_results: list[dict],
    evidence_validation: dict
) -> dict:
    """
    Generate a grounded support response using Groq LLM.
    
    Returns:
        {
          "reply": str,
          "evidence_used": list[str],
          "confidence_note": str,
          "method": str
        }
    """
    client = _get_client()

    if client is None:
        return _fallback_response(customer_message, intent, retrieval_results)

    intent_desc = get_intent_description(intent)
    evidence_context = _build_evidence_context(retrieval_results)
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    user_prompt = f"""Customer message: "{customer_message}"

Detected intent: {intent} ({intent_desc})
Intent confidence: {intent_confidence:.0%}
Evidence quality: {evidence_validation.get('quality', 'moderate')}

{evidence_context}

Generate a helpful Apple Support response grounded in the historical evidence above."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()

        # Extract JSON
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                reply = result.get("reply", "").strip()
                if reply:
                    evidence_used = [str(x) for x in result.get("evidence_used", [])]
                    return {
                        "reply": reply,
                        "evidence_used": evidence_used,
                        "confidence_note": result.get("confidence_note", ""),
                        "method": "llm_groq"
                    }
            except json.JSONDecodeError:
                pass
        
        # If full JSON parse failed but raw text contains reply, extract via regex
        reply_match = re.search(r'"reply"\s*:\s*"(.*?)(?:"\s*,\s*"|"\s*\})', raw, re.DOTALL)
        if reply_match:
            reply_text = reply_match.group(1).encode('utf-8').decode('unicode_escape', errors='replace')
            evidence_ids = [str(r["conversation_id"]) for r in retrieval_results[:2]]
            return {
                "reply": reply_text,
                "evidence_used": evidence_ids,
                "confidence_note": "Recovered from partial JSON response",
                "method": "llm_groq"
            }
    except Exception as e:
        print(f"[Generator] LLM error: {e}, using fallback")

    return _fallback_response(customer_message, intent, retrieval_results)


def _fallback_response(customer_message: str, intent: str, retrieval_results: list[dict]) -> dict:
    """Template-based fallback when LLM is unavailable."""
    templates = {
        "ios_update_issue": "Thank you for reaching out! iOS update issues can be frustrating. Please try restarting your device and going to Settings > General > Software Update. If the problem persists, please DM us with your iOS version so we can investigate further. We're here to help! 🍎",
        "battery_drain": "We understand how concerning battery drain can be! Please go to Settings > Battery to check which apps are consuming the most power. Also try Settings > General > Background App Refresh and disable it for unused apps. DM us your iOS version and device model for more specific help!",
        "app_crash": "Sorry to hear your app is crashing! Please try: 1) Force-close the app, 2) Restart your device, 3) Check for app updates in the App Store. If the issue persists, DM us with the app name and your iOS version. We'd love to help! 🍎",
        "wifi_connectivity": "We're sorry about the WiFi issues! Please try Settings > General > Transfer or Reset iPhone > Reset > Reset Network Settings. Note: this will reset saved Wi-Fi passwords. DM us if you need more help with your specific setup!",
        "device_performance": "We'd like to help with your device performance. Please try restarting your iPhone and checking Settings > General > iPhone Storage for space issues. A factory reset may also help. DM us with your device model and iOS version for personalized assistance!",
        "account_access": "We understand account access issues can be stressful! Please visit iforgot.apple.com to reset your Apple ID password. For additional help, DM us and we'll guide you through account recovery securely.",
        "account_security": "This requires immediate attention from our security team. Please call Apple Support directly or visit apple.com/support for urgent account security matters. Do not share your credentials with anyone.",
        "billing_payment": "We take billing concerns very seriously. Please review your purchase history in Settings > [Your Name] > Media & Purchases > View Account. For disputed charges, DM us your Apple ID (not your password) so we can assist you.",
        "hardware_issue": "We're sorry to hear about the hardware issue. Depending on your warranty status, this may be covered by Apple. Please visit apple.com/support to check repair options or find an Apple Store near you. DM us if you need more guidance!",
        "general_question": "Thank you for reaching out to Apple Support! We're happy to help. Please DM us with more details about your question or visit apple.com/support for instant answers to common questions. 🍎"
    }

    reply = templates.get(intent, templates["general_question"])
    evidence_ids = [r["conversation_id"] for r in retrieval_results[:2]] if retrieval_results else []

    return {
        "reply": reply,
        "evidence_used": evidence_ids,
        "confidence_note": "Response generated from template (LLM unavailable).",
        "method": "template_fallback"
    }
