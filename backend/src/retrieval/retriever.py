"""
RAG Retriever — finds top-K most similar historical Apple Support conversations
using TF-IDF cosine similarity.
Includes evidence validation to assess retrieval confidence.
"""

import sys
import numpy as np
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.retrieval.index import get_index

# Thresholds for evidence validation
MIN_SIMILARITY_THRESHOLD = 0.10   # Below this → weak evidence
GOOD_SIMILARITY_THRESHOLD = 0.30  # Above this → strong evidence


def retrieve(query: str, top_k: int = 5, exclude_ids: set = None) -> dict:
    """
    Retrieve the top-K most similar historical conversations for a given query.

    Args:
        query: Customer message to search for.
        top_k: Number of results to return.
        exclude_ids: Set of conversation_ids to exclude (prevent evaluation leakage).

    Returns:
        {
          "query": str,
          "results": [{"conversation_id", "similarity", "customer_message", "brand_response"}, ...],
          "retrieval_confidence": float,
          "evidence_quality": str  ("strong" | "moderate" | "weak")
        }
    """
    index_data = get_index()
    if index_data is None:
        return {
            "query": query,
            "results": [],
            "retrieval_confidence": 0.0,
            "evidence_quality": "weak",
            "error": "Index not built yet"
        }

    vectorizer = index_data["vectorizer"]
    matrix = index_data["matrix"]
    conversations = index_data["conversations"]

    # Transform query to TF-IDF vector
    query_vec = vectorizer.transform([query])

    # Compute cosine similarities
    similarities = cosine_similarity(query_vec, matrix).flatten()

    # Get sorted indices (descending)
    sorted_indices = np.argsort(similarities)[::-1]

    results = []
    seen_ids = exclude_ids or set()

    for idx in sorted_indices:
        if len(results) >= top_k:
            break
        conv = conversations[idx]
        conv_id = conv.get("conversation_id", str(idx))
        if conv_id in seen_ids:
            continue
        sim = float(similarities[idx])
        if sim < 0.001:  # Skip near-zero similarity
            continue
        results.append({
            "conversation_id": conv_id,
            "similarity": round(sim, 4),
            "customer_message": conv["customer_message"],
            "brand_response": conv["brand_response"],
        })

    # Evidence validation
    if results:
        max_sim = results[0]["similarity"]
        avg_sim = sum(r["similarity"] for r in results) / len(results)
    else:
        max_sim = 0.0
        avg_sim = 0.0

    # Retrieval confidence: normalized combination of max and avg similarity
    retrieval_confidence = round(min(1.0, (max_sim * 0.7 + avg_sim * 0.3) * 2.5), 3)

    if max_sim >= GOOD_SIMILARITY_THRESHOLD:
        evidence_quality = "strong"
    elif max_sim >= MIN_SIMILARITY_THRESHOLD:
        evidence_quality = "moderate"
    else:
        evidence_quality = "weak"

    return {
        "query": query,
        "results": results,
        "retrieval_confidence": retrieval_confidence,
        "evidence_quality": evidence_quality,
        "top_similarity": round(max_sim, 4),
        "avg_similarity": round(avg_sim, 4),
        "num_results": len(results)
    }


def validate_evidence(retrieval_result: dict, intent_confidence: float) -> dict:
    """
    Validate whether retrieved evidence is sufficient for response generation.

    Returns:
        {
          "sufficient": bool,
          "evidence_confidence": float,
          "validation_notes": str
        }
    """
    top_sim = retrieval_result.get("top_similarity", 0.0)
    retrieval_conf = retrieval_result.get("retrieval_confidence", 0.0)
    quality = retrieval_result.get("evidence_quality", "weak")
    num_results = retrieval_result.get("num_results", 0)

    notes = []
    sufficient = True

    if quality == "weak":
        sufficient = False
        notes.append("Low retrieval similarity — weak historical evidence")
    if intent_confidence < 0.50:
        sufficient = False
        notes.append("Low intent confidence — ambiguous customer message")
    if num_results == 0:
        sufficient = False
        notes.append("No historical conversations retrieved")

    evidence_confidence = round(
        retrieval_conf * 0.6 + intent_confidence * 0.4, 3
    )

    return {
        "sufficient": sufficient,
        "evidence_confidence": evidence_confidence,
        "validation_notes": "; ".join(notes) if notes else "Evidence sufficient for response generation",
        "quality": quality
    }


if __name__ == "__main__":
    result = retrieve("My battery is draining so fast after iOS update")
    print(f"Evidence Quality: {result['evidence_quality']}")
    print(f"Retrieval Confidence: {result['retrieval_confidence']}")
    for r in result["results"]:
        print(f"  [{r['similarity']:.3f}] {r['customer_message'][:80]}")
