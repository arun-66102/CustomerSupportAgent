"""
Response Quality Evaluator using LLM-as-a-Judge (Groq / llama-3.3-70b-versatile).
Scores generated responses on 6 dimensions using a 1-5 scale.
Also computes weighted overall score and per-example breakdown.
"""

import os
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

_groq_client = None

# Dimension weights (must sum to 1.0)
SCORE_WEIGHTS = {
    "correctness": 0.25,
    "groundedness": 0.20,
    "relevance": 0.20,
    "helpfulness": 0.20,
    "brand_consistency": 0.10,
    "safety": 0.05
}


def _get_client():
    global _groq_client
    api_key = os.getenv("GROQ_API_KEY", "")
    if _groq_client is None and GROQ_AVAILABLE and api_key:
        _groq_client = Groq(api_key=api_key)
    return _groq_client


JUDGE_SYSTEM = """You are an expert evaluator of customer support responses for Apple Support.
Evaluate the given response on 6 dimensions using a scale of 1-5.

Scoring:
1 = Very Poor, 2 = Poor, 3 = Acceptable, 4 = Good, 5 = Excellent

Dimensions:
- correctness: Is the advice technically accurate and not misleading?
- groundedness: Is the response grounded in the historical evidence provided?
- relevance: Does the response address the customer's specific issue?
- helpfulness: Would this response actually help the customer resolve their issue?
- brand_consistency: Does this sound like professional Apple Support communication?
- safety: Does the response avoid giving dangerous, harmful, or inappropriate advice?

Respond ONLY with valid JSON:
{
  "correctness": <1-5>,
  "groundedness": <1-5>,
  "relevance": <1-5>,
  "helpfulness": <1-5>,
  "brand_consistency": <1-5>,
  "safety": <1-5>,
  "reasoning": "<brief explanation>"
}"""


def score_response(
    customer_message: str,
    generated_response: str,
    retrieval_evidence: list[dict],
    intent: str
) -> dict:
    """Score a single generated response using the LLM judge."""
    client = _get_client()

    if client is None or not generated_response:
        return _fallback_score(generated_response)

    evidence_text = "\n".join([
        f"Evidence {i+1}: Customer: {r['customer_message'][:100]}... | Response: {r['brand_response'][:100]}..."
        for i, r in enumerate(retrieval_evidence[:3])
    ]) or "No historical evidence available."

    user_prompt = f"""Customer message: "{customer_message}"
Detected intent: {intent}
Historical evidence used:
{evidence_text}

Generated Apple Support response to evaluate:
"{generated_response}"

Evaluate this response on all 6 dimensions."""

    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                scores = json.loads(json_match.group())
                scores = _validate_scores(scores)
                scores["overall"] = _compute_overall(scores)
                scores["method"] = "llm_judge"
                return scores
            except json.JSONDecodeError:
                pass
    except Exception as e:
        print(f"[ResponseEval] LLM judge error: {e}")

    return _fallback_score(generated_response)


def _validate_scores(scores: dict) -> dict:
    """Ensure all scores are integers in [1, 5]."""
    dimensions = ["correctness", "groundedness", "relevance", "helpfulness", "brand_consistency", "safety"]
    for dim in dimensions:
        val = scores.get(dim, 3)
        try:
            val = int(val)
        except (TypeError, ValueError):
            val = 3
        scores[dim] = max(1, min(5, val))
    return scores


def _compute_overall(scores: dict) -> float:
    """Compute weighted overall score (scale 1-5)."""
    total = sum(
        scores.get(dim, 3) * weight
        for dim, weight in SCORE_WEIGHTS.items()
    )
    return round(total, 2)


def _fallback_score(response: str) -> dict:
    """Return neutral scores if LLM judge is unavailable."""
    if not response:
        scores = {d: 1 for d in SCORE_WEIGHTS}
    else:
        # Heuristic: response length indicates effort
        score = 3 if len(response) > 50 else 2
        scores = {d: score for d in SCORE_WEIGHTS}
    scores["overall"] = _compute_overall(scores)
    scores["reasoning"] = "LLM judge unavailable — neutral scores assigned."
    scores["method"] = "heuristic_fallback"
    return scores


def evaluate_responses(
    pipeline_outputs: list[dict],
    golden_examples: list[dict]
) -> dict:
    """
    Evaluate all generated responses over the golden set.
    
    Args:
        pipeline_outputs: list of full pipeline output dicts (one per golden example)
        golden_examples: list of golden example dicts
    
    Returns:
        Aggregate response quality metrics.
    """
    all_scores = []
    per_example_scores = []

    for output, golden in zip(pipeline_outputs, golden_examples):
        gen_resp = output.get("generated_response", {})
        reply = gen_resp.get("reply", "") if isinstance(gen_resp, dict) else str(gen_resp)
        retrieval = output.get("retrieval", {}).get("results", [])
        intent = output.get("intent", {}).get("intent", "general_question")

        scores = score_response(
            customer_message=golden["message"],
            generated_response=reply,
            retrieval_evidence=retrieval,
            intent=intent
        )
        all_scores.append(scores)
        per_example_scores.append({
            "id": golden["id"],
            "message": golden["message"][:80],
            "intent": intent,
            "reply_preview": reply[:100],
            "scores": scores
        })

    if not all_scores:
        return {"error": "No responses to evaluate"}

    dimensions = ["correctness", "groundedness", "relevance", "helpfulness", "brand_consistency", "safety"]
    averages = {}
    for dim in dimensions:
        vals = [s[dim] for s in all_scores if isinstance(s.get(dim), (int, float))]
        averages[dim] = round(sum(vals) / len(vals), 2) if vals else 0

    avg_overall = round(sum(s["overall"] for s in all_scores) / len(all_scores), 2)

    return {
        "average_scores": averages,
        "average_overall": avg_overall,
        "score_weights": SCORE_WEIGHTS,
        "per_example": per_example_scores,
        "total_evaluated": len(all_scores)
    }
