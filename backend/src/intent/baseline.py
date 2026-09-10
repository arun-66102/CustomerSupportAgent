"""
Baseline intent classifiers for comparison:
1. Majority class baseline (always predicts most frequent intent)
2. TF-IDF + Logistic Regression baseline
"""

import os
import sys
import json
import pickle
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.intent.taxonomy import INTENT_LABELS

BASELINE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "baselines"
TFIDF_MODEL_FILE = BASELINE_DIR / "tfidf_model.pkl"


class MajorityClassBaseline:
    """Always predicts the most frequent class in training data."""

    def __init__(self):
        self.majority_class = "ios_update_issue"  # Most common Apple Support intent

    def predict(self, message: str) -> dict:
        return {
            "intent": self.majority_class,
            "confidence": 0.30,
            "reasoning": "Majority class baseline — always predicts most frequent intent.",
            "method": "majority_class"
        }

    def predict_batch(self, messages: list[str]) -> list[dict]:
        return [self.predict(m) for m in messages]


class TFIDFBaseline:
    """TF-IDF + Logistic Regression classifier trained on labeled data."""

    def __init__(self):
        self.model = None
        self.vectorizer = None
        self._load_or_skip()

    def _load_or_skip(self):
        """Load pre-trained model if it exists."""
        if TFIDF_MODEL_FILE.exists():
            try:
                with open(TFIDF_MODEL_FILE, "rb") as f:
                    data = pickle.load(f)
                self.vectorizer = data["vectorizer"]
                self.model = data["model"]
                print("[TFIDFBaseline] Loaded pre-trained model.")
            except Exception as e:
                print(f"[TFIDFBaseline] Could not load model: {e}")

    def train(self, messages: list[str], labels: list[str]):
        """Train the TF-IDF + LR model on labeled data."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline

        BASELINE_DIR.mkdir(parents=True, exist_ok=True)

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=10000,
            sublinear_tf=True,
            min_df=1
        )
        self.model = LogisticRegression(max_iter=500, C=1.0, class_weight="balanced")

        X = self.vectorizer.fit_transform(messages)
        self.model.fit(X, labels)

        # Save model
        with open(TFIDF_MODEL_FILE, "wb") as f:
            pickle.dump({"vectorizer": self.vectorizer, "model": self.model}, f)
        print(f"[TFIDFBaseline] Trained and saved model to {TFIDF_MODEL_FILE}")

    def predict(self, message: str) -> dict:
        if self.model is None or self.vectorizer is None:
            return {
                "intent": "general_question",
                "confidence": 0.30,
                "reasoning": "TF-IDF model not trained yet.",
                "method": "tfidf_untrained"
            }
        X = self.vectorizer.transform([message])
        intent = self.model.predict(X)[0]
        proba = self.model.predict_proba(X)[0]
        confidence = float(max(proba))
        return {
            "intent": intent,
            "confidence": round(confidence, 3),
            "reasoning": f"TF-IDF + Logistic Regression prediction.",
            "method": "tfidf_lr"
        }

    def predict_batch(self, messages: list[str]) -> list[dict]:
        if self.model is None or self.vectorizer is None:
            return [self.predict(m) for m in messages]
        X = self.vectorizer.transform(messages)
        intents = self.model.predict(X)
        probas = self.model.predict_proba(X)
        return [
            {
                "intent": intent,
                "confidence": round(float(max(proba)), 3),
                "reasoning": "TF-IDF + Logistic Regression prediction.",
                "method": "tfidf_lr"
            }
            for intent, proba in zip(intents, probas)
        ]


# Singletons
_majority_baseline = None
_tfidf_baseline = None


def get_majority_baseline() -> MajorityClassBaseline:
    global _majority_baseline
    if _majority_baseline is None:
        _majority_baseline = MajorityClassBaseline()
    return _majority_baseline


def get_tfidf_baseline() -> TFIDFBaseline:
    global _tfidf_baseline
    if _tfidf_baseline is None:
        _tfidf_baseline = TFIDFBaseline()
    return _tfidf_baseline
