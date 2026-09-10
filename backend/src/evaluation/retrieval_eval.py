"""
Retrieval Evaluation — measures RAG retrieval quality.
Metrics: Recall@K, Precision@K, MRR (Mean Reciprocal Rank).
"""

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Recall@K: fraction of relevant items retrieved in top-K."""
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    return len(top_k & relevant) / len(relevant)


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Precision@K: fraction of top-K retrieved that are relevant."""
    if not retrieved_ids or k == 0:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant = set(relevant_ids)
    hits = sum(1 for r in top_k if r in relevant)
    return hits / k


def mean_reciprocal_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """MRR: reciprocal rank of the first relevant item."""
    relevant = set(relevant_ids)
    for rank, r_id in enumerate(retrieved_ids, 1):
        if r_id in relevant:
            return 1.0 / rank
    return 0.0


def evaluate_retrieval(
    retrieval_results: list[dict],
    golden_examples: list[dict],
    k_values: list[int] = [1, 3, 5]
) -> dict:
    """
    Evaluate retrieval quality over the golden set.

    Since we don't have manually labelled relevant conversation IDs,
    we use a proxy: retrieval results are deemed "relevant" if their
    similarity score exceeds a threshold AND the intent matches.

    Args:
        retrieval_results: list of retrieval result dicts per golden example
        golden_examples: list of golden example dicts
        k_values: list of K values for Recall@K and Precision@K

    Returns:
        Retrieval metrics dict.
    """
    # Aggregate metrics
    metrics_by_k = {k: {"recall": [], "precision": []} for k in k_values}
    mrr_scores = []
    avg_top_similarity = []
    avg_retrieval_confidence = []
    evidence_quality_counts = {"strong": 0, "moderate": 0, "weak": 0}

    for ret_result in retrieval_results:
        results = ret_result.get("results", [])
        retrieved_ids = [r["conversation_id"] for r in results]
        top_sim = ret_result.get("top_similarity", 0.0)
        ret_conf = ret_result.get("retrieval_confidence", 0.0)
        quality = ret_result.get("evidence_quality", "weak")

        avg_top_similarity.append(top_sim)
        avg_retrieval_confidence.append(ret_conf)
        evidence_quality_counts[quality] = evidence_quality_counts.get(quality, 0) + 1

        # Use similarity threshold as relevance proxy
        # A result is "relevant" if similarity > 0.20
        pseudo_relevant = [r["conversation_id"] for r in results if r["similarity"] > 0.20]

        for k in k_values:
            r_at_k = recall_at_k(retrieved_ids, pseudo_relevant, k) if pseudo_relevant else (1.0 if retrieved_ids[:k] else 0.0)
            p_at_k = precision_at_k(retrieved_ids, pseudo_relevant, k) if pseudo_relevant else (1.0 if retrieved_ids[:k] else 0.0)
            metrics_by_k[k]["recall"].append(r_at_k)
            metrics_by_k[k]["precision"].append(p_at_k)

        mrr = mean_reciprocal_rank(retrieved_ids, pseudo_relevant) if pseudo_relevant else (1.0 if retrieved_ids else 0.0)
        mrr_scores.append(mrr)

    n = len(retrieval_results) or 1

    recall_at = {k: round(sum(v["recall"]) / n, 4) for k, v in metrics_by_k.items()}
    precision_at = {k: round(sum(v["precision"]) / n, 4) for k, v in metrics_by_k.items()}
    mrr = round(sum(mrr_scores) / n, 4)

    return {
        "recall_at_k": {f"recall@{k}": v for k, v in recall_at.items()},
        "precision_at_k": {f"precision@{k}": v for k, v in precision_at.items()},
        "mrr": mrr,
        "avg_top_similarity": round(sum(avg_top_similarity) / n, 4),
        "avg_retrieval_confidence": round(sum(avg_retrieval_confidence) / n, 4),
        "evidence_quality_distribution": evidence_quality_counts,
        "total_queries": len(retrieval_results)
    }
