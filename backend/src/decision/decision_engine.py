"""
Decision Engine — determines whether to AUTO-HANDLE or ESCALATE.
Uses a risk-aware policy based on intent confidence, retrieval evidence, and risk level.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.intent.taxonomy import get_intent_risk, HIGH_RISK_INTENTS, MEDIUM_RISK_INTENTS

# Decision thresholds (tunable)
MIN_INTENT_CONFIDENCE = 0.60     # Below this → escalate
MIN_RETRIEVAL_CONFIDENCE = 0.20  # Below this → escalate (weak evidence)
MIN_EVIDENCE_CONFIDENCE = 0.25   # Combined evidence threshold


def decide(
    intent: str,
    intent_confidence: float,
    retrieval_result: dict,
    evidence_validation: dict,
    generated_response: dict = None
) -> dict:
    """
    Make the AUTO-HANDLE vs ESCALATE decision.

    Decision policy (in order of priority):
    1. HIGH risk intent → always ESCALATE
    2. Low intent confidence (<0.60) → ESCALATE
    3. Weak evidence (retrieval_confidence < 0.20) → ESCALATE
    4. MEDIUM risk + insufficient evidence → ESCALATE
    5. Otherwise → AUTO-HANDLE

    Returns:
        {
          "decision": "AUTO-HANDLE" | "ESCALATE",
          "reason": str,
          "confidence_factors": dict,
          "risk_level": str
        }
    """
    risk = get_intent_risk(intent)
    retrieval_confidence = retrieval_result.get("retrieval_confidence", 0.0)
    evidence_confidence = evidence_validation.get("evidence_confidence", 0.0)
    evidence_sufficient = evidence_validation.get("sufficient", False)
    evidence_quality = retrieval_result.get("evidence_quality", "weak")

    confidence_factors = {
        "intent": intent,
        "intent_confidence": round(intent_confidence, 3),
        "risk_level": risk,
        "retrieval_confidence": round(retrieval_confidence, 3),
        "evidence_confidence": round(evidence_confidence, 3),
        "evidence_quality": evidence_quality,
        "evidence_sufficient": evidence_sufficient,
    }

    # Rule 1: High risk → always escalate
    if risk == "HIGH":
        return {
            "decision": "ESCALATE",
            "reason": f"Intent '{intent}' is high-risk (potential financial or security issue). Human agent required.",
            "confidence_factors": confidence_factors,
            "risk_level": risk
        }

    # Rule 2: Low intent confidence
    if intent_confidence < MIN_INTENT_CONFIDENCE:
        return {
            "decision": "ESCALATE",
            "reason": f"Intent confidence too low ({intent_confidence:.0%} < {MIN_INTENT_CONFIDENCE:.0%}). Customer message may be ambiguous.",
            "confidence_factors": confidence_factors,
            "risk_level": risk
        }

    # Rule 3: Weak retrieval evidence
    if retrieval_confidence < MIN_RETRIEVAL_CONFIDENCE:
        return {
            "decision": "ESCALATE",
            "reason": f"Insufficient historical evidence (retrieval confidence {retrieval_confidence:.2f} < {MIN_RETRIEVAL_CONFIDENCE}). Cannot generate a reliable response.",
            "confidence_factors": confidence_factors,
            "risk_level": risk
        }

    # Rule 4: Medium risk + insufficient evidence
    if risk == "MEDIUM" and not evidence_sufficient:
        return {
            "decision": "ESCALATE",
            "reason": f"Medium-risk intent '{intent}' with insufficient supporting evidence. Escalating for safety.",
            "confidence_factors": confidence_factors,
            "risk_level": risk
        }

    # Rule 5: AUTO-HANDLE
    return {
        "decision": "AUTO-HANDLE",
        "reason": f"High-confidence intent ({intent_confidence:.0%}), {evidence_quality} historical evidence, and low/acceptable risk — safe to auto-respond.",
        "confidence_factors": confidence_factors,
        "risk_level": risk
    }


def get_decision_explanation(decision_result: dict) -> str:
    """Return a human-readable explanation of the decision."""
    d = decision_result["decision"]
    r = decision_result["reason"]
    risk = decision_result.get("risk_level", "UNKNOWN")
    cf = decision_result.get("confidence_factors", {})

    lines = [
        f"**Decision:** {d}",
        f"**Reason:** {r}",
        f"**Risk Level:** {risk}",
        f"**Intent Confidence:** {cf.get('intent_confidence', 0):.0%}",
        f"**Retrieval Confidence:** {cf.get('retrieval_confidence', 0):.2f}",
        f"**Evidence Quality:** {cf.get('evidence_quality', 'N/A')}",
    ]
    return "\n".join(lines)
