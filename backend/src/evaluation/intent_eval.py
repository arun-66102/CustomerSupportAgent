"""
Intent Evaluation — measures intent classification quality against the golden set.
Metrics: Accuracy, Precision, Recall, Macro F1, Confusion Matrix, Per-intent breakdown.
Compares: LLM classifier vs Majority baseline vs TF-IDF baseline.
"""

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    confusion_matrix, classification_report
)
from src.intent.taxonomy import INTENT_LABELS


def evaluate_intent(
    predictions: list[dict],
    golden_examples: list[dict]
) -> dict:
    """
    Evaluate intent classification performance.

    Args:
        predictions: list of {"intent": str, "confidence": float, ...}
        golden_examples: list of {"id": str, "intent": str, ...}

    Returns:
        Comprehensive metrics dict.
    """
    assert len(predictions) == len(golden_examples), "Predictions and golden set must have same length"

    y_true = [ex["intent"] for ex in golden_examples]
    y_pred = [p["intent"] for p in predictions]
    confidences = [p.get("confidence", 0.5) for p in predictions]

    # Overall metrics
    accuracy = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    macro_precision = precision_score(y_true, y_pred, average="macro", zero_division=0)
    macro_recall = recall_score(y_true, y_pred, average="macro", zero_division=0)

    # Per-class metrics
    labels_present = sorted(set(y_true + y_pred))
    per_class_report = classification_report(
        y_true, y_pred,
        labels=labels_present,
        output_dict=True,
        zero_division=0
    )

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=labels_present)

    # Per-intent breakdown (simplified)
    per_intent = {}
    for label in labels_present:
        metrics = per_class_report.get(label, {})
        per_intent[label] = {
            "precision": round(metrics.get("precision", 0), 3),
            "recall": round(metrics.get("recall", 0), 3),
            "f1": round(metrics.get("f1-score", 0), 3),
            "support": int(metrics.get("support", 0))
        }

    # Confidence calibration — avg confidence for correct vs incorrect
    correct_confidences = [c for c, t, p in zip(confidences, y_true, y_pred) if t == p]
    wrong_confidences = [c for c, t, p in zip(confidences, y_true, y_pred) if t != p]
    avg_conf_correct = sum(correct_confidences) / len(correct_confidences) if correct_confidences else 0
    avg_conf_wrong = sum(wrong_confidences) / len(wrong_confidences) if wrong_confidences else 0

    # Detailed per-example results
    per_example = []
    for ex, pred in zip(golden_examples, predictions):
        correct = ex["intent"] == pred["intent"]
        per_example.append({
            "id": ex["id"],
            "message": ex["message"],
            "true_intent": ex["intent"],
            "predicted_intent": pred["intent"],
            "confidence": round(pred.get("confidence", 0), 3),
            "correct": correct,
            "difficulty": ex.get("difficulty", "medium"),
            "method": pred.get("method", "unknown")
        })

    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "per_intent": per_intent,
        "confusion_matrix": {
            "labels": labels_present,
            "matrix": cm.tolist()
        },
        "confidence_calibration": {
            "avg_confidence_correct": round(avg_conf_correct, 3),
            "avg_confidence_wrong": round(avg_conf_wrong, 3)
        },
        "per_example": per_example,
        "total_examples": len(golden_examples),
        "correct_count": sum(1 for e in per_example if e["correct"])
    }


def compare_baselines(
    llm_predictions: list[dict],
    majority_predictions: list[dict],
    tfidf_predictions: list[dict],
    golden_examples: list[dict]
) -> dict:
    """Compare LLM vs baselines on the golden set."""
    llm_metrics = evaluate_intent(llm_predictions, golden_examples)
    majority_metrics = evaluate_intent(majority_predictions, golden_examples)
    tfidf_metrics = evaluate_intent(tfidf_predictions, golden_examples)

    return {
        "comparison_table": [
            {
                "system": "Majority Class Baseline",
                "accuracy": f"{majority_metrics['accuracy']:.1%}",
                "macro_f1": f"{majority_metrics['macro_f1']:.1%}",
                "method": "majority_class"
            },
            {
                "system": "TF-IDF + Logistic Regression",
                "accuracy": f"{tfidf_metrics['accuracy']:.1%}",
                "macro_f1": f"{tfidf_metrics['macro_f1']:.1%}",
                "method": "tfidf_lr"
            },
            {
                "system": "LLM (llama-3.3-70b)",
                "accuracy": f"{llm_metrics['accuracy']:.1%}",
                "macro_f1": f"{llm_metrics['macro_f1']:.1%}",
                "method": "llm"
            }
        ],
        "llm": llm_metrics,
        "majority": majority_metrics,
        "tfidf": tfidf_metrics
    }
