"""
Full end-to-end pipeline orchestrator.
Runs: Intent → Retrieval → Evidence Validation → LLM Generation → Decision
"""

import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.intent.classifier import classify_intent_llm
from src.retrieval.retriever import retrieve, validate_evidence
from src.generation.generator import generate_response
from src.decision.decision_engine import decide


def run_pipeline(
    customer_message: str,
    top_k: int = 5,
    exclude_ids: set = None
) -> dict:
    """
    Run the full support pipeline for a customer message.

    Args:
        customer_message: Raw customer message text.
        top_k: Number of historical conversations to retrieve.
        exclude_ids: Set of conversation IDs to exclude from retrieval (prevents eval leakage).

    Returns:
        Complete pipeline output with all intermediate steps.
    """
    start_time = time.time()
    pipeline_trace = []

    # ── Step 1: Intent Classification ─────────────────────────────────────
    t0 = time.time()
    intent_result = classify_intent_llm(customer_message)
    pipeline_trace.append({
        "step": "intent_classification",
        "duration_ms": round((time.time() - t0) * 1000, 1),
        "output": intent_result
    })

    # ── Step 2: RAG Retrieval ──────────────────────────────────────────────
    t0 = time.time()
    retrieval_result = retrieve(
        query=customer_message,
        top_k=top_k,
        exclude_ids=exclude_ids
    )
    pipeline_trace.append({
        "step": "rag_retrieval",
        "duration_ms": round((time.time() - t0) * 1000, 1),
        "output": {
            "evidence_quality": retrieval_result["evidence_quality"],
            "retrieval_confidence": retrieval_result["retrieval_confidence"],
            "top_similarity": retrieval_result.get("top_similarity", 0),
            "num_results": retrieval_result["num_results"]
        }
    })

    # ── Step 3: Evidence Validation ────────────────────────────────────────
    t0 = time.time()
    evidence_validation = validate_evidence(
        retrieval_result=retrieval_result,
        intent_confidence=intent_result["confidence"]
    )
    pipeline_trace.append({
        "step": "evidence_validation",
        "duration_ms": round((time.time() - t0) * 1000, 1),
        "output": evidence_validation
    })

    # ── Step 4: LLM Response Generation ───────────────────────────────────
    t0 = time.time()
    generated_response = generate_response(
        customer_message=customer_message,
        intent=intent_result["intent"],
        intent_confidence=intent_result["confidence"],
        retrieval_results=retrieval_result.get("results", []),
        evidence_validation=evidence_validation
    )
    pipeline_trace.append({
        "step": "response_generation",
        "duration_ms": round((time.time() - t0) * 1000, 1),
        "output": {
            "method": generated_response.get("method"),
            "evidence_used_count": len(generated_response.get("evidence_used", []))
        }
    })

    # ── Step 5: Decision Engine ────────────────────────────────────────────
    t0 = time.time()
    decision_result = decide(
        intent=intent_result["intent"],
        intent_confidence=intent_result["confidence"],
        retrieval_result=retrieval_result,
        evidence_validation=evidence_validation,
        generated_response=generated_response
    )
    pipeline_trace.append({
        "step": "decision_engine",
        "duration_ms": round((time.time() - t0) * 1000, 1),
        "output": {
            "decision": decision_result["decision"],
            "risk_level": decision_result["risk_level"]
        }
    })

    total_ms = round((time.time() - start_time) * 1000, 1)

    return {
        "customer_message": customer_message,
        "intent": intent_result,
        "retrieval": retrieval_result,
        "evidence_validation": evidence_validation,
        "generated_response": generated_response,
        "decision": decision_result,
        "pipeline_trace": pipeline_trace,
        "total_duration_ms": total_ms,
        # Final output for the user
        "final_reply": generated_response.get("reply", ""),
        "final_decision": decision_result["decision"],
        "decision_reason": decision_result["reason"]
    }


if __name__ == "__main__":
    # Quick test
    test_messages = [
        "My iPhone battery drains so fast after the iOS 17 update",
        "Someone hacked my Apple ID and I can't get in",
        "How do I enable dark mode?",
    ]

    from src.retrieval.index import get_index
    if get_index() is None:
        print("Index not built yet. Run the startup sequence first.")
    else:
        for msg in test_messages:
            print(f"\n{'='*60}")
            result = run_pipeline(msg)
            print(f"Message: {msg}")
            print(f"Intent: {result['intent']['intent']} ({result['intent']['confidence']:.0%})")
            print(f"Evidence Quality: {result['retrieval']['evidence_quality']}")
            print(f"Decision: {result['final_decision']}")
            print(f"Reply: {result['final_reply'][:100]}...")
            print(f"Duration: {result['total_duration_ms']}ms")
