"""
Decision Engine Evaluation — measures AUTO-HANDLE vs ESCALATE decision quality.
Key metrics: Accuracy, Precision, Recall, F1, False Auto-Handle Rate, Escalation Recall.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)


def evaluate_decisions(
    decision_outputs: list[dict],
    golden_examples: list[dict]
) -> dict:
    """
    Evaluate decision engine performance against golden set expected decisions.

    Args:
        decision_outputs: list of decision dicts {"decision": "AUTO-HANDLE"|"ESCALATE", ...}
        golden_examples: list of golden example dicts with "expected_decision"

    Returns:
        Comprehensive decision metrics.
    """
    y_true = [ex["expected_decision"] for ex in golden_examples]
    y_pred = [d["decision"] for d in decision_outputs]

    accuracy = accuracy_score(y_true, y_pred)

    # Treat AUTO-HANDLE as positive (we care about correct auto-handling)
    labels = ["AUTO-HANDLE", "ESCALATE"]
    precision = precision_score(y_true, y_pred, pos_label="AUTO-HANDLE", zero_division=0)
    recall = recall_score(y_true, y_pred, pos_label="AUTO-HANDLE", zero_division=0)
    f1 = f1_score(y_true, y_pred, pos_label="AUTO-HANDLE", zero_division=0)

    # Confusion matrix: rows=actual, cols=predicted
    # [AUTO-HANDLE][AUTO-HANDLE] = TP (correct auto)
    # [AUTO-HANDLE][ESCALATE]    = FN (missed auto → unnecessary escalation)
    # [ESCALATE][AUTO-HANDLE]    = FP (FALSE AUTO-HANDLE — dangerous!)
    # [ESCALATE][ESCALATE]       = TN (correct escalation)
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    if len(cm) == 2:
        tp = int(cm[0][0])  # Correct AUTO-HANDLE
        fn = int(cm[0][1])  # Unnecessary escalation
        fp = int(cm[1][0])  # FALSE AUTO-HANDLE (most dangerous)
        tn = int(cm[1][1])  # Correct ESCALATE
    else:
        tp = fn = fp = tn = 0

    # False Auto-Handle Rate = FP / (FP + TN)
    # Measures: of all cases that SHOULD be escalated, how many did we auto-handle?
    false_auto_handle_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    # Escalation Recall = TN / (TN + FP)  [same as above inverted]
    escalation_recall = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    # Per-example breakdown
    per_example = []
    for ex, pred_dec in zip(golden_examples, decision_outputs):
        correct = ex["expected_decision"] == pred_dec["decision"]
        is_false_auto = (ex["expected_decision"] == "ESCALATE" and pred_dec["decision"] == "AUTO-HANDLE")
        per_example.append({
            "id": ex["id"],
            "message": ex["message"][:80],
            "expected": ex["expected_decision"],
            "predicted": pred_dec["decision"],
            "correct": correct,
            "false_auto_handle": is_false_auto,
            "reason": pred_dec.get("reason", ""),
            "risk_level": pred_dec.get("risk_level", ""),
            "difficulty": ex.get("difficulty", "medium")
        })

    # False auto-handle examples for failure analysis
    false_auto_examples = [e for e in per_example if e["false_auto_handle"]]

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_auto_handle_rate": round(false_auto_handle_rate, 4),
        "escalation_recall": round(escalation_recall, 4),
        "confusion_matrix": {
            "labels": labels,
            "matrix": cm.tolist(),
            "tp_correct_auto": tp,
            "fn_unnecessary_escalation": fn,
            "fp_false_auto_handle": fp,
            "tn_correct_escalation": tn
        },
        "per_example": per_example,
        "false_auto_handle_cases": false_auto_examples,
        "total_examples": len(golden_examples),
        "correct_count": sum(1 for e in per_example if e["correct"])
    }
